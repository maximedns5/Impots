"""Weighted totals and the distributional table (§4.5).

Two outputs, and deliberately only two:

  * an **aggregate** per instrument — what the reform raises or costs nationally;
  * **deciles of niveau de vie** — who gains and who loses, and by how much.

No top-1 % row. Branch A' has no capital income and a wage distribution drawn
from published margins, so the top of the distribution is a construction; a
top-percentile figure would be the least reliable number in the model presented
as the most interesting one. §4.2 rules it out and this module does not provide it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from impots.guards import sector_balance
from impots.population import margins as _margins

#: A reform moves a household by less than this and we call it unaffected. Below
#: about ten euros a year the answer is dominated by rounding inside the engine
#: and by the arbitrariness of a synthetic income, not by the reform.
INDIFFERENCE_EUR = 10.0

N_DECILES = 10

#: Instruments reported as national totals, in the order a reader wants them.
INSTRUMENTS = (
    "salaire_brut", "salaire_super_brut", "salaire_net", "salaire_imposable",
    "cotisations_salariales", "cotisations_employeur",
    "retraite_imposable", "chomage_brut",
    "csg_deductible", "csg_imposable", "crds", "csg_ij", "csg_retraite", "csg_chomage",
    "csg_non_salarie", "revenus_non_salaries", "revenus_non_salaries_hors_gerants",
    "allegement_general", "allegement_bandeau_maladie", "allegement_bandeau_famille",
    # What separates super-brut minus brut from D121, for the grid (but 19, étape 1).
    "prelevements_salaires_d291", "pension_employeur_etat", "remuneration_hors_brut",
    "ir",
    "ir_avant_niches", "reductions", "credits_impot", "cdhr",
    "af", "ppa", "rsa", "aide_logement", "reduction_loyer_solidarite", "aefa", "cf", "asf",
    "crds_pfam", "crds_logement", "crds_mini", "revenu_disponible",
    # The full-take-up entitlements, beside the expected payments that carry the plain
    # names (but 19, étape 4, `runner._serve_in_expectation`): read by the lines that
    # compare an entitlement through the Drees bridge, never summed into a cost.
    "rsa_droit", "ppa_droit", "crds_mini_droit", "aefa_droit", "revenu_disponible_droit",
    # The consumption taxes, only when the consumption is imputed (D-323): receipts the
    # state collects that disposable income, taken before indirect taxes, does not show.
    "tva_menages", "accises_energie", "consommation_imputee",
)
#: The instruments assis sur les salaires, which the totals and the reform costs carry
#: to France's employees (étape « extrapolation », décision du propriétaire du
#: 10 novembre 2026). The survey sees 25,29 M employees, the national accounts count
#: 27,18 M; each wage stays at its published value, and each non-gérant employee's
#: wage-borne amounts count `margins.EXTRAPOLATION_SALARIES` times (1,0747) in a total
#: and in a delta. The runner writes, per ménage, `{key}_hors_champ`: what its members
#: stand for beyond themselves.
#:
#: **What is not carried, and why.** `salaire_imposable` and the income tax: their base
#: is calibrated on the salaries the foyers declare (`margins.DECLARED_TAXABLE_WAGES`,
#: met to 0,1 % on the survey's field), so carrying it would count the declared salaries
#: 7,5 % twice; a reform's income-tax feedback is that of the declared salaries, which
#: the survey's field already reaches (counting it, and the prime's, for the missing too
#: would take 0,9 Md€ off the 60,9 of Attal's « droit au brut », 15 000 ménages, droit
#: 2024). The benefits (prime d'activité, RSA, aides au logement), the pensions, the
#: unemployment benefit and the CSG on them, and every niveau de vie, decile and
#: household's own figure: they are the surveyed households', whom the survey weights to
#: France already. The gérants, whose declared pay is the whole of theirs.
#:
#: `revenu_disponible` is carried by its net wages alone (`salaire_net`'s part), so that
#: a reform's cost, Δ disposable income less Δ employers' contributions, stays the sum of
#: its instruments' deltas (`guards.sector_balance`); its deciles are not.
ASSIS_SUR_LES_SALAIRES = (
    "salaire_brut", "salaire_super_brut", "salaire_net",
    "cotisations_salariales", "cotisations_employeur",
    "csg_deductible", "csg_imposable", "crds",
    "allegement_general", "allegement_bandeau_maladie", "allegement_bandeau_famille",
    "prelevements_salaires_d291", "pension_employeur_etat", "remuneration_hors_brut",
)
#: The suffix of the runner's per-ménage extrapolation columns.
HORS_CHAMP = "_hors_champ"
#: Which carried column each total reads; the disposable incomes by their net wages.
_PORTE_PAR = {**{name: name for name in ASSIS_SUR_LES_SALAIRES},
              "revenu_disponible": "salaire_net", "revenu_disponible_droit": "salaire_net"}
#: The setting a page reads to say the hypothesis; off, the totals are the survey's.
EXTRAPOLER_SALARIES = True
#: The sentence a public page says (étape « extrapolation »).
PHRASE_EXTRAPOLATION = (
    "Les cotisations, la CSG et les allègements sur les salaires, et le coût des réformes "
    "qui les touchent, sont portés aux 27,2 millions de salariés de la France entière, en "
    "supposant les 1,9 million que l'enquête Emploi ne voit pas semblables aux autres ; "
    "l'impôt sur le revenu, les prestations et les niveaux de vie restent ceux des "
    "ménages enquêtés.")

#: The receipts on consumption: a fall in them is a cost, and a loss of purchasing power
#: for the household that pays them.
CONSOMMATION = ("tva_menages", "accises_energie")

#: Weighted counts rather than euro totals — reported alongside, never summed in.
COUNTS = ("n_foyers", "n_foyers_imposes", "n_persons", "n_dependants",
          "n_foyers_tmi_0", "n_foyers_tmi_1", "n_foyers_tmi_2", "n_foyers_tmi_3",
          "n_foyers_tmi_4",
          "n_allocataires_af", "n_allocataires_ppa", "n_allocataires_rsa",
          "n_allocataires_aide_logement",
          # Expected payees in December, Σ p over the entitled familles (étape 4).
          "n_allocataires_rsa_servi", "n_allocataires_ppa_servi")


def consumption_units(n_aged_14_plus: np.ndarray, n_children_under_14: np.ndarray) -> np.ndarray:
    """OECD-modified equivalence scale: 1 for the first adult, 0.5 for each further
    person aged 14 or over, 0.3 for each child under 14.

    This is the scale INSEE uses for "niveau de vie", which is what makes our
    deciles comparable with Filosofi's published ones. A household of one adult
    always scores 1.0 even if the arithmetic is written as `1 + 0.5 x 0`.
    """
    adults = np.maximum(np.asarray(n_aged_14_plus, dtype=np.float64), 1.0)
    children = np.asarray(n_children_under_14, dtype=np.float64)
    return 1.0 + 0.5 * (adults - 1.0) + 0.3 * children


def weighted_quantiles(
    values: np.ndarray, weights: np.ndarray, quantiles: np.ndarray
) -> np.ndarray:
    """Quantiles of a weighted distribution.

    Population quantiles, not sample ones: each household stands for `weight`
    households, so the cumulative weight is what gets cut, using the midpoint
    convention that keeps the median of a symmetric distribution in the middle.
    """
    order = np.argsort(values, kind="stable")
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    cutpoints = (cumulative - 0.5 * sorted_weights) / cumulative[-1]
    return np.interp(quantiles, cutpoints, sorted_values)


def weighted_decile_index(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Assign each household to a decile by weighted RANK, not by value cut.

    Cutting on values breaks when the ranking variable has ties, and disposable
    income has plenty: households living on the same benefit land on the same
    euro. With value cuts two adjacent decile boundaries can coincide, and the
    decile between them comes out **empty** — the table silently prints nine rows
    where a reader expects ten. Ranking on cumulative weight always yields ten
    groups of equal weight; tied households are split between deciles in survey
    order, which is arbitrary but unbiased.
    """
    order = np.argsort(values, kind="stable")
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    position = (cumulative - 0.5 * ordered_weights) / cumulative[-1]
    sorted_decile = np.minimum((position * N_DECILES).astype(np.int64), N_DECILES - 1)
    decile = np.empty_like(sorted_decile)
    decile[order] = sorted_decile
    return decile


@dataclass
class DecileRow:
    decile: int
    n_households: float
    """Weighted count."""
    mean_niveau_de_vie: float
    mean_baseline: float
    mean_reform: float | None
    mean_delta: float | None
    share_winners: float | None
    share_losers: float | None
    share_unaffected: float | None


@dataclass
class Aggregates:
    totals: dict[str, float]
    """Weighted national total per instrument, in EUR."""
    counts: dict[str, float] = field(default_factory=dict)
    """Weighted counts (foyers, foyers imposés, persons, dependants)."""
    niveau_de_vie_quantiles: dict[int, float] = field(default_factory=dict)
    """p10/p50/p90 of niveau de vie, PERSON-weighted, in EUR — keyed by percentile.

    Separate from `deciles` on purpose, and the two must not be confused. `deciles`
    ranks and weights by HOUSEHOLD, which is what a reform's incidence table needs.
    INSEE's published niveau de vie statistics are person-weighted QUANTILES, so
    reconciling against them needs this. The reconciliation lines read decile MEANS
    against published quantiles until the zero-masked sweep, and that wrong estimator
    was the larger half of both residuals — on the report's own run, roughly -12 %
    against -5 % on the median and +39 % against +4 % on D9/D1, more than any
    modelling gap. The lines compute the comparison from their own pass rather than
    quoting these, for the reason in D-072.
    """
    totals_reform: dict[str, float] = field(default_factory=dict)
    deltas: dict[str, float] = field(default_factory=dict)
    deciles: list[DecileRow] = field(default_factory=list)
    households: float = 0.0
    persons: float = 0.0
    reform_cost: float | None = None
    """Positive = the reform costs the public finances; negative = it raises money.

    Two terms, and for a long time only one of them. Household disposable income is
    what the state hands over on the household side. But an employer-contribution
    reform changes what the state COLLECTS without moving disposable income at all —
    the gain lands on the firm — so a cost measured on households alone reported
    exactly zero for a reform costing 17.7 bn. Both terms are counted now (D-039)."""
    balance: dict[str, float] = field(default_factory=dict)
    """Double-entry check (D-045): the reported cost against the same figure
    reconstituted from the individual instrument deltas."""
    niveau_de_vie_quantiles_droit: dict[int, float] = field(default_factory=dict)
    """The same quantiles at full take-up, from `revenu_disponible_droit`: what the
    reconciliation and the grid compared before the take-up layer (D-363), kept so their
    existing lines read the same concept until a new one is preregistered. Empty when the
    frame has no entitlement column."""
    reform_cost_droit: float | None = None
    """The cost at full take-up, the difference of two entitlements: what every cost was
    before the take-up layer. Reported beside `reform_cost`, never instead of it."""
    extrapolation_salaires: float = 1.0
    """The factor the totals assis sur les salaires were carried by
    (`margins.EXTRAPOLATION_SALARIES`), 1 when the frame has no `_hors_champ` column or
    `EXTRAPOLER_SALARIES` is off: what a page reads to say the hypothesis."""
    employer_contribution_delta: float = 0.0
    """Change in employer contributions actually paid, net of allègements. Derived as
    Δ(salaire_super_brut − salaire_brut) rather than from `cotisations_employeur`,
    which is gross of the allègements and therefore does not move when one changes."""


def _total(frame: pl.DataFrame, column: str, weights: np.ndarray) -> float:
    return float((frame[column].to_numpy() * weights).sum())


def extrapole(frame: pl.DataFrame, column: str, weights: np.ndarray) -> float:
    """The weighted total of `column` (`name` or `name_reform`), carried to France's
    employees when the instrument is assis sur les salaires (`ASSIS_SUR_LES_SALAIRES`):
    plus what its `_hors_champ` column holds. A frame without that column (a runner
    before the étape « extrapolation », a hand-made frame) is the survey's."""
    total = _total(frame, column, weights)
    reform = column.endswith("_reform")
    name = column.removesuffix("_reform")
    if not EXTRAPOLER_SALARIES or name not in _PORTE_PAR:
        return total
    carried = f"{_PORTE_PAR[name]}{HORS_CHAMP}" + ("_reform" if reform else "")
    if carried not in frame.columns:
        return total
    return total + _total(frame, carried, weights)


def _employer_contribution_delta(frame: pl.DataFrame, weights: np.ndarray) -> float:
    """Change in employer contributions paid, net of allègements.

    `cotisations_employeur` is gross of the allègements, so it does not move when one
    changes — it showed a delta of exactly zero for a reform that cut labour cost by
    17.7 bn. The difference between super-brut and brut is what is actually paid.
    """
    needed = ("salaire_super_brut", "salaire_brut",
              "salaire_super_brut_reform", "salaire_brut_reform")
    if not all(column in frame.columns for column in needed):
        return 0.0
    paid = (extrapole(frame, "salaire_super_brut", weights)
            - extrapole(frame, "salaire_brut", weights))
    paid_reform = (
        extrapole(frame, "salaire_super_brut_reform", weights)
        - extrapole(frame, "salaire_brut_reform", weights)
    )
    return paid_reform - paid


def _public_cost(deltas: dict[str, float], employer_delta: float) -> float | None:
    """What the reform costs the public finances, both sides of it.

    Households gain what the state gives up, so Δ disposable income is a cost as it
    stands. Employers paying LESS means the state collects less, so a negative
    employer delta is also a cost — hence the subtraction.
    """
    household = deltas.get("revenu_disponible")
    conso = sum(deltas.get(name, 0.0) for name in CONSOMMATION)
    if household is None and not employer_delta and not any(
            name in deltas for name in CONSOMMATION):
        return None
    return (household or 0.0) - employer_delta - conso


def aggregate(result_households: pl.DataFrame) -> Aggregates:
    """Weighted totals and the decile table from a `RunResult.households` frame."""
    frame = result_households
    weights = frame["weight"].to_numpy().astype(np.float64)
    has_reform = any(column.endswith("_reform") for column in frame.columns)

    totals = {
        name: extrapole(frame, name, weights) for name in INSTRUMENTS if name in frame.columns
    }
    carried = EXTRAPOLER_SALARIES and f"salaire_brut{HORS_CHAMP}" in frame.columns
    factor = _margins.EXTRAPOLATION_SALARIES.value if carried else 1.0
    counts = {
        name: _total(frame, name, weights) for name in COUNTS if name in frame.columns
    }
    totals_reform: dict[str, float] = {}
    deltas: dict[str, float] = {}
    employer_delta = _employer_contribution_delta(frame, weights)
    if has_reform:
        for name in totals:
            reform_column = f"{name}_reform"
            if reform_column in frame.columns:
                totals_reform[name] = extrapole(frame, reform_column, weights)
                deltas[name] = totals_reform[name] - totals[name]
    # AFTER the deltas exist, not before: computed above, `cost` read an empty dict
    # and came back None for every reform without an employer term.
    cost = _public_cost(deltas, employer_delta)
    cost_droit = None
    if cost is not None and "revenu_disponible_droit" in deltas:
        cost_droit = _public_cost(
            {**deltas, "revenu_disponible": deltas["revenu_disponible_droit"]},
            employer_delta)

    units = consumption_units(
        frame["n_aged_14_plus"].to_numpy(), frame["n_children_under_14"].to_numpy()
    )
    # Niveau de vie needs disposable income, which only the full tier computes.
    # Ranking on anything else would silently produce a different distribution.
    if "revenu_disponible" not in frame.columns:
        return Aggregates(
            totals=totals, counts=counts, totals_reform=totals_reform, deltas=deltas,
            households=float(weights.sum()),
            persons=float((frame["n_persons"].to_numpy() * weights).sum()),
            employer_contribution_delta=employer_delta, extrapolation_salaires=factor,
            reform_cost=cost, reform_cost_droit=cost_droit,
            balance=(
                sector_balance(deltas, reform_cost=cost,
                               employer_contribution_delta=employer_delta)
                if cost is not None else {}
            ),
        )

    baseline = frame["revenu_disponible"].to_numpy().astype(np.float64)
    niveau_de_vie = baseline / units
    decile_index = weighted_decile_index(niveau_de_vie, weights)

    # Person-weighted, because a niveau de vie quantile describes PEOPLE: a published
    # median is the person in the middle, not the household in the middle.
    person_weights = weights * frame["n_persons"].to_numpy().astype(np.float64)
    cuts = weighted_quantiles(niveau_de_vie, person_weights, np.array([0.1, 0.5, 0.9]))
    quantiles = {10: float(cuts[0]), 50: float(cuts[1]), 90: float(cuts[2])}
    quantiles_droit: dict[int, float] = {}
    if "revenu_disponible_droit" in frame.columns:
        droit = frame["revenu_disponible_droit"].to_numpy().astype(np.float64) / units
        cuts = weighted_quantiles(droit, person_weights, np.array([0.1, 0.5, 0.9]))
        quantiles_droit = {10: float(cuts[0]), 50: float(cuts[1]), 90: float(cuts[2])}

    reform_values = (
        frame["revenu_disponible_reform"].to_numpy().astype(np.float64)
        if "revenu_disponible_reform" in frame.columns
        else None
    )
    delta = None if reform_values is None else reform_values - baseline
    if delta is not None:
        # What the household loses in consumption taxes, at constant volumes (D-323):
        # its purchasing power moves by disposable income less those taxes.
        for name in CONSOMMATION:
            if f"{name}_reform" in frame.columns:
                paid = (frame[f"{name}_reform"].to_numpy().astype(np.float64)
                        - frame[name].to_numpy().astype(np.float64))
                delta = delta - paid
                reform_values = reform_values - paid

    rows: list[DecileRow] = []
    for index in range(N_DECILES):
        mask = decile_index == index
        w = weights[mask]
        total_weight = w.sum()
        if total_weight == 0:  # pragma: no cover - only on a degenerate sample
            continue
        row = DecileRow(
            decile=index + 1,
            n_households=float(total_weight),
            mean_niveau_de_vie=float((niveau_de_vie[mask] * w).sum() / total_weight),
            mean_baseline=float((baseline[mask] * w).sum() / total_weight),
            mean_reform=None,
            mean_delta=None,
            share_winners=None,
            share_losers=None,
            share_unaffected=None,
        )
        if delta is not None:
            d = delta[mask]
            row.mean_reform = float((reform_values[mask] * w).sum() / total_weight)
            row.mean_delta = float((d * w).sum() / total_weight)
            row.share_winners = float(w[d > INDIFFERENCE_EUR].sum() / total_weight)
            row.share_losers = float(w[d < -INDIFFERENCE_EUR].sum() / total_weight)
            row.share_unaffected = float(w[np.abs(d) <= INDIFFERENCE_EUR].sum() / total_weight)
        rows.append(row)

    return Aggregates(
        totals=totals,
        counts=counts,
        niveau_de_vie_quantiles=quantiles,
        niveau_de_vie_quantiles_droit=quantiles_droit,
        totals_reform=totals_reform,
        deltas=deltas,
        deciles=rows,
        households=float(weights.sum()),
        persons=float((frame["n_persons"].to_numpy() * weights).sum()),
        # A reform that raises disposable income costs the budget that much.
        employer_contribution_delta=employer_delta, extrapolation_salaires=factor,
        reform_cost=cost, reform_cost_droit=cost_droit,
        balance=(
            sector_balance(deltas, reform_cost=cost,
                           employer_contribution_delta=employer_delta)
            if cost is not None else {}
        ),
    )
