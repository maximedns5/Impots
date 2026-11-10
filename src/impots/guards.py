"""Assertions that turn silent wrongness into a stack trace.

Every defect in the Phase 0/1 audit's table that mattered had the same shape:
plausible numbers, no exception, all existing guards green. Two of them were
weighting bugs, and both changed every aggregate in the model by a factor:

* household weight taken as the **sum** of member weights rather than the mean —
  implied a population of 120 M and multiplied every euro total by 2.2;
* a PPS subsample **rescaled on top of** a design that is already self-weighting,
  multiplying every aggregate by 2.8.

Neither raised anything. Neither was caught by a NaN check or a range check,
because the numbers stayed finite and positive. What would have caught both is
the observation that a *reweighting step must not change what the weights add up
to* — so that is what `weight_identity` asserts, and PHASE2_SPEC §3.5 requires it
around every weighting step in the firm module.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import polars as pl


class GuardError(RuntimeError):
    """A guard fired. The number was wrong in a way that would not have raised."""


class WeightIdentityError(GuardError):
    """A weighting step changed a total it had no business changing."""


def weighted_total(frame: pl.DataFrame, column: str, weight: str = "weight") -> float:
    """`sum(column * weight)` — the quantity a reweighting must preserve."""
    return float((frame[column].to_numpy() * frame[weight].to_numpy()).sum())


def weight_identity(
    before: pl.DataFrame,
    after: pl.DataFrame,
    columns: Sequence[str],
    *,
    step: str,
    weight: str = "weight",
    targets: dict[str, float] | None = None,
    rtol: float = 1e-6,
) -> dict[str, float]:
    """Assert a weighting step preserved the totals it should have.

    For each column, the weighted total after the step must equal the total
    before it — or, where the step *is* a calibration, the target it was fitted
    to. Returns the totals after, so a caller can log them.

    `targets` names the columns the step was allowed to move, and to what. A
    column that is neither preserved nor targeted is exactly the case both
    historical defects fell into.
    """
    targets = targets or {}
    after_totals: dict[str, float] = {}
    problems: list[str] = []

    for column in columns:
        was = weighted_total(before, column, weight)
        now = weighted_total(after, column, weight)
        after_totals[column] = now
        expected = targets.get(column, was)
        if expected == 0:
            if abs(now) > rtol:
                problems.append(f"{column}: expected 0, got {now:,.6g}")
            continue
        drift = abs(now / expected - 1.0)
        if drift > rtol:
            kind = "calibration target" if column in targets else "pre-step total"
            problems.append(
                f"{column}: {now:,.6g} against a {kind} of {expected:,.6g} "
                f"({now / expected - 1:+.4%})"
            )

    if problems:
        raise WeightIdentityError(
            f"the weighting step {step!r} moved totals it should not have — this is "
            "the shape of a bug that produces plausible numbers and raises nothing:\n  "
            + "\n  ".join(problems)
        )
    return after_totals


def no_nan(values: np.ndarray, name: str) -> np.ndarray:
    """Refuse non-finite output.

    Zero-income households legitimately make openfisca emit divide-by-zero
    RuntimeWarnings; the results stay finite. A NaN is not noise — it is how a
    broken entity join first announced itself in Phase 1.
    """
    bad = int((~np.isfinite(values)).sum())
    if bad:
        raise GuardError(
            f"{name} produced {bad} non-finite values of {values.size} — a wiring bug, "
            "not an edge case"
        )
    return values


def non_negative(values: np.ndarray, name: str) -> np.ndarray:
    bad = int((values < 0).sum())
    if bad:
        raise GuardError(f"{name} has {bad} negative values of {values.size}")
    return values


def not_greater(
    smaller: np.ndarray, larger: np.ndarray, name: str, tolerance: float = 0.0
) -> int:
    """Count violations of `smaller <= larger` without raising.

    Some relations are near-identities that real data breaks in a few cells —
    value added should not exceed turnover, but published sector aggregates
    occasionally say otherwise. Those are worth counting and reporting, not worth
    aborting a build over. Returns the count so the caller can decide.
    """
    return int((smaller > larger + tolerance).sum())


# --------------------------------------------------------------------------- #
# Double-entry: every euro a reform moves has to land somewhere (D-045)
# --------------------------------------------------------------------------- #
#: Household-side instruments the state RECEIVES. Positive delta = the state collects
#: more. Signs are normalised upstream in `engine.outputs`, so these are all the same
#: way round here.
STATE_RECEIPTS = (
    "ir", "csg_imposable", "csg_deductible", "crds", "cotisations_salariales",
    # The consumption taxes, when the consumption is imputed (D-323).
    "tva_menages", "accises_energie",
    # Not in `ir`, and zero unless capital income is imputed (D-248). `pfu` is NOT here:
    # it is a part of `ir`, and counting it twice is the failure this ledger catches.
    "prelevements_sociaux_capital",
    # Not in `ir` either, from 2025: the CDHR tops a high income's tax up to 20 % of its
    # RFR, PFU included, and takes back part of a PFU cut. Zero without capital income;
    # with it, a PFU cut moved disposable income by 17,7 % less than `ir` (D-250).
    "cdhr",
    # The CSG on the sick pay, which correction 23 levies (D-306): not in the salary's CSG
    # rows. Without it the first pass of a CSG rate on the allowances was refused, its
    # 467,7 M€ held by no instrument (D-307).
    "csg_ij",
    # The CSG of the non-salariés, whose income the population carries since but 19
    # (étape 2): a reform of the CSG rate moved their disposable income with no receipt to
    # hold it, and the real-population balance test failed by it.
    "csg_non_salarie",
)

#: Household-side instruments the state PAYS. Positive delta = the state pays more.
#: `aefa` — the prime de Noël — joined this list when the prestations knobs arrived.
#: It is not a benefit anyone reforms directly, but it rides on RSA ELIGIBILITY, so any
#: reform that moves the RSA threshold moves it too. Leaving it out made a national RSA
#: reform miss by 0.99 %, which is what the guard is for.
#: The CRDS entries are NEGATIVE as openfisca stores them, and they belong here rather
#: than among the receipts: a household's benefit is `gross + crds`, `revenu_disponible`
#: uses the net figure, and the population reports the gross one. Netting them here
#: makes the reconstitution the state's actual burden. Without them a national AF
#: reform missed by 0.50 % — five times the tolerance, and exactly 0.5 % of the AF
#: moved, which is the CRDS rate.
#: NOT `crds_logement`, and the reason is the same rule read the other way: openfisca
#: builds `aide_logement` from `aide_logement_montant`, which is `brut + crds_logement`,
#: so the aid is reported ALREADY net and disposable income moves by exactly it. Netting
#: its CRDS here counted it twice, unseen until the first population pass of a housing
#: reform (PLF 2027 art. 74), which missed by +0.52 % (D-299).
STATE_TRANSFERS = ("af", "ppa", "rsa", "aide_logement", "aefa", "cf", "asf",
                   "crds_pfam", "crds_mini")

#: The identity is checked in absolute euros against a floor, and relatively above it.
#: A reform moving a few million is not worth a relative test; one moving billions is.
BALANCE_FLOOR_EUR = 5.0e6

#: How much of a reform's effect may run through instruments the runner does not
#: report before the identity refuses.
#:
#: It is not zero, and the reason is worth stating. `revenu_disponible` is computed by
#: OpenFisca over the whole benefits cascade, which is wider than the handful of
#: instruments this runner reports: a CSG rise pulls a little through the complément
#: familial, the ARS and the minima that have no row of their own. Measured, that
#: leakage is 0.066 % of a 10.4 bn CSG reform. The floor sits at 0.1 %, an order of
#: magnitude below the failure this guard exists for — the 17.7 bn labour-cost reform
#: whose public cost read zero, which breaches it by 100 %.
BALANCE_RTOL = 1e-3

#: The same allowance, expressed against the reform's GROSS movement instead of its net.
#:
#: BALANCE_RTOL was always meant as «a share of the reform's size», and
#: `max(|reform_cost|, |expected_cost|)` is a fine proxy for size — right up until a
#: reform offsets itself. F2's budget-neutral solver builds such reforms ON PURPOSE:
#: it root-finds the knob value that drives the net to zero, so at exactly the iterate
#: the user cares about, the proxy collapses and a fixed leakage is divided by nothing.
#:
#: That is not hypothetical. The first real solve — RSA socle at 700 EUR, paid for by
#: the CSG — failed the guard at its third evaluation with «+0.57 %» on an unexplained
#: 305 719 EUR, while the instruments had moved 3.7 bn each way.
#:
#: MEASURED, ACROSS FIVE REFORMS, at 8 000 households (D-093):
#:
#:     réforme               brut       net        résidu      /brut
#:     rsa 700              3.545 md   +3 545 M   303 660 EUR  8.57e-05
#:     csg +0,5 pt          5.625 md   -5 245 M     2 188 EUR  3.89e-07
#:     rsa 700 + csg 2,9    9.171 md   -1 699 M   305 868 EUR  3.34e-05
#:     rsa 700 + csg 3,05  10.862 md   -3 268 M   307 200 EUR  2.83e-05
#:     décote 60 %          1.909 md   -1 909 M       -30 EUR -1.59e-08
#:
#: The residual is CONSTANT at about 305 000 EUR wherever the RSA arm appears and
#: vanishes where it does not — it is that arm's leakage through unreported instruments,
#: exactly what BALANCE_RTOL exists to tolerate, and it does not shrink because a second
#: arm cancels the headline. Only the denominator moves.
#:
#: 3e-4 is three and a half times the largest ratio measured. It is TIGHTER than
#: BALANCE_RTOL, so it never relaxes a reform the net test already judged: it is a
#: second allowance that only binds where the net test has stopped meaning anything.
BALANCE_GROSS_RTOL = 3e-4

#: The firm side's own gross allowance, and it is 300 times tighter — because the two
#: sides tolerate different things.
#:
#: The household identity sanctions LEAKAGE: `revenu_disponible` runs through the whole
#: benefits cascade, wider than the instruments the runner reports, so a real reform
#: leaves a real residual (measured up to 8.55e-05 of gross). The firm identity sanctions
#: nothing of the kind: `prelevements_entreprise` is an OpenFisca formula and
#: FIRM_COMPONENTS is a second, independent route to the same number, so an instrument in
#: one and not the other IS the bug to catch. The only benign residual is float
#: accumulation.
#:
#: MEASURED, four firm reforms on the real 2023 cells at period 2026:
#:
#:     IS 25 -> 30 %      15.526 md brut   -843 EUR    5.43e-08
#:     C3S x2              5.289 md brut    +18 EUR    3.31e-09
#:     IS 30 % + CVAE 0   17.886 md brut   -539 EUR    3.01e-08
#:     IS 26 % + CVAE 0    5.465 md brut    +43 EUR    7.79e-09   (net -745 M: the
#:                                                                 near-neutral shape)
#:
#: 1e-6 is roughly eighteen times the worst of those. Reusing BALANCE_GROSS_RTOL here
#: would have bought 12 M EUR of allowance on a 40 bn offsetting reform and swallowed a
#: genuine 5 M EUR instrument leaking outside FIRM_COMPONENTS — which the old net-scaled
#: guard caught. A relaxation justified by household leakage has no business on a side
#: that has none.
FIRM_BALANCE_GROSS_RTOL = 1e-6


#: The niche outputs a reform can move. If a reform touches a niche knob and these are
#: zero across the population, the reform's cost is zero because the DATA is missing,
#: not because the instrument does nothing.
NICHE_TOTALS = ("reductions", "credits_impot")


#: Knobs that need WITHIN-DECILE dispersion, which the imputation cannot supply.
#:
#: The global cap binds only on foyers claiming more than 10 000 EUR. The imputation
#: gives every claimant in a decile the same base — a count and a total are all the
#: DGFiP publishes — so the largest imputed credit is a decile mean, about 1 900 EUR in
#: the top decile, and NOBODY reaches the cap. Measured: with bases imputed, moving the
#: cap from 10 000 to 4 000 still costs exactly 0.000 bn.
#:
#: So this knob keeps returning a confident zero after imputation has silenced the flag
#: for every other niche, which is the worse failure: a warning that goes away without
#: the problem going away.
DISPERSION_DEPENDENT_KNOBS = frozenset({"plafond_global_niches"})


def niche_blind_spot(
    knobs: Iterable[str], totals: dict[str, float], niche_knobs: Iterable[str],
    *, bases_are_imputed: bool = False,
) -> tuple[str, ...]:
    """Niche knobs this reform moves that the population cannot answer for.

    The most dangerous output this project could produce is a confident zero. A reader
    who cuts the home-help credit from 50 % to 30 % and is told the reform costs
    0 EUR will conclude the credit is worthless; the truth is that the synthetic
    population declares no home-help spending at all, so there is nothing for the rate
    to apply to. The 19.53 bn of réductions and crédits nationally is money this
    population has no way to express.

    Returns the offending knobs, empty when there is nothing to warn about — either
    because the reform touches no niche, or because the population has bases.
    """
    touched = tuple(sorted(set(knobs) & set(niche_knobs)))
    if not touched:
        return ()
    declared = sum(abs(totals.get(name, 0.0)) for name in NICHE_TOTALS)
    if declared <= 0.0:
        return touched
    # Bases exist, so most knobs can now be priced. The ones that need a tail cannot:
    # a decile-mean imputation has no dispersion, and the cap only ever binds in the
    # tail it does not have.
    if bases_are_imputed:
        return tuple(sorted(set(touched) & DISPERSION_DEPENDENT_KNOBS))
    return ()


class ZeroConfiantError(GuardError, ValueError):
    """Une passe a chiffré un bouton qui ne pouvait pas bouger sur elle."""


def zero_confiant(knobs: Iterable[str], imputees: Iterable[str],
                  totals: dict[str, float]) -> dict[str, str]:
    """Les boutons d'une réforme qu'une passe de population ne peut pas chiffrer, chacun
    avec sa raison ; vide quand il n'y a rien à dire.

    La garde des niches (`niche_blind_spot`), généralisée à tout ce que la population ne
    porte qu'imputé (but 14) : un bouton du capital sans le capital imputé, de la
    consommation sans la consommation, des IJ sans les IJ, et l'IFI toujours, puisque la
    population ne porte aucun patrimoine. Chacun y coûterait un zéro confiant. `imputees`
    sont les noms de ce que la passe a imputé (`imputations.Imputations.noms`), `totals`
    ses agrégats de référence, où les niches lisent leurs bases déclarées. Une fonction
    pure : chaque chemin décide de ce qu'il en fait, l'API un drapeau pour les niches, les
    autres un refus (`refuse_zero_confiant`)."""
    from impots import consommation
    from impots.engine.reforms import CAPITAL_KNOBS, NICHE_KNOBS
    from impots.population import imputations as imp

    knobs = frozenset(knobs)
    imputees = frozenset(imputees)
    aveugles: dict[str, str] = {}
    sans = {imp.CAPITAL: (knobs & CAPITAL_KNOBS, "le capital n'est pas imputé (D-249)"),
            imp.CONSOMMATION: (knobs & set(consommation.BOUTONS),
                               "la consommation n'est pas imputée (D-323)"),
            imp.IJ: (knobs & imp.IJ_KNOBS, "les IJ ne sont pas imputées (D-305)")}
    for nom, (touches, raison) in sans.items():
        if nom not in imputees:
            aveugles.update(dict.fromkeys(sorted(touches), raison))
    aveugles.update(dict.fromkeys(
        sorted(knobs & imp.ifi_knobs()),
        "la population ne porte aucun patrimoine (porte « patrimoine »)"))
    niches = niche_blind_spot(knobs, totals, NICHE_KNOBS,
                              bases_are_imputed=imp.NICHES in imputees)
    aveugles.update(dict.fromkeys(
        niches, "la population ne déclare pas cette base, ou la dispersion que le "
                "plafond lit (D-064, D-075)"))
    return aveugles


def refuse_zero_confiant(knobs: Iterable[str], imputees: Iterable[str],
                         totals: dict[str, float], *, chemin: str) -> None:
    """Refuse, avec chaque raison, une passe dont un bouton ne pouvait pas bouger."""
    aveugles = zero_confiant(knobs, imputees, totals)
    if aveugles:
        raise ZeroConfiantError(
            f"{chemin} : " + " ; ".join(f"`{knob}` ne bouge pas, {raison}"
                                        for knob, raison in aveugles.items())
            + ". Son coût serait un zéro par absence d'assiette, non par absence d'effet.")


class CoutAbsentError(GuardError):
    """Une passe chiffrée n'a pas de coût calculé."""


def cout_calcule(reform_cost: float | None, *, chemin: str) -> float:
    """Le coût d'une passe chiffrée, ou un refus : jamais un `None` changé en zéro.

    `reform_cost` n'est `None` que pour une passe sans réforme ; un chemin qui attend un
    coût et le trouve absent a un défaut de câblage, que `reform_cost or 0.0` cachait
    derrière un coût nul (audit du but 14, annexe 2, § 4.6)."""
    if reform_cost is None:
        raise CoutAbsentError(
            f"{chemin} : la passe n'a pas de coût calculé (aucune réforme n'y a tourné) ; "
            f"un coût absent n'est pas un coût nul.")
    return float(reform_cost)


class SectorBalanceError(RuntimeError):
    """A reform's reported cost does not match what the instruments say moved."""


def sector_balance(
    deltas: dict[str, float],
    *,
    reform_cost: float,
    employer_contribution_delta: float = 0.0,
    aggregate_deltas: dict[str, float] | None = None,
    rtol: float = BALANCE_RTOL,
    gross_rtol: float = BALANCE_GROSS_RTOL,
    floor: float = BALANCE_FLOOR_EUR,
) -> dict[str, float]:
    """Assert that the reported public cost equals what the instruments say moved.

    **The first version of this guard did not work, and how it failed is the point.**
    It asserted `households + firms + state = 0` with the state's side written in
    terms of the firm's — so removing the firm term moved both sides together and the
    identity balanced at zero. It could not have caught the bug it was written for.
    That is the D-044 shape again, appearing inside the guard meant to enforce it: a
    check is only as good as its independence from the thing it checks.

    The bug was never an accounting *inconsistency*. The accounting was consistent;
    `reform_cost` simply reported one sector out of two. So the thing to check is not
    that the sectors balance — they will, being derived from each other — but that the
    **headline figure agrees with the sum of the instruments**, which is assembled
    here and computed elsewhere.

    A reform that moves 17.7 bn of labour cost and reports a public cost of zero
    breaches this by 100 %.
    """
    aggregate_deltas = aggregate_deltas or {}
    # An instrument present on BOTH sides would be counted twice, and the identity would
    # then demand a headline that double-counts it — a breach the guard would blame on
    # the headline. Refused by name (§2.2, M2): the aggregate layer is a SEPARATE set of
    # instruments, never a second spelling of a micro one.
    collision = sorted(set(aggregate_deltas) & (set(STATE_RECEIPTS) | set(STATE_TRANSFERS)))
    if collision:
        raise SectorBalanceError(
            f"instrument(s) {collision} présent(s) à la fois dans les postes micro et "
            f"dans la couche agrégée : ils seraient comptés DEUX FOIS, et l'identité "
            f"réclamerait alors un coût annoncé qui les double lui aussi. La couche "
            f"agrégée est un jeu d'instruments distinct, jamais une seconde orthographe.")

    receipts = sum(deltas.get(name, 0.0) for name in STATE_RECEIPTS)
    transfers = sum(deltas.get(name, 0.0) for name in STATE_TRANSFERS)
    # Bucket B receipts, entering with the same sign convention as the micro ones: more
    # collected is a gain to the state.
    aggregate = sum(aggregate_deltas.values())
    # What the state collects, across both sides. Employers paying less is a fall in
    # receipts, so the delta enters with its own sign.
    state_gain = (receipts - transfers + employer_contribution_delta
                  + aggregate)
    # A cost to the state is the negative of what it gains.
    expected_cost = -state_gain
    unexplained = reform_cost - expected_cost

    # The reform's SIZE: the sum of the ABSOLUTE movements, instrument by instrument.
    #
    # NOT `abs(receipts) + abs(transfers)`, which is what the first version of this fix
    # computed and which is wrong in exactly the case the fix was written for. Those two
    # are already SUMS over their buckets, so a reform whose arms sit in the SAME bucket
    # — RSA up, AF down, both transfers — has them cancel before the abs() ever runs. On
    # a real such reform the bucket form read 2.713 bn against a true movement of
    # 5.165 bn, and in the extreme (rsa +3.673 bn, af -3.670 bn) it read 3.0 M against
    # 7.34 bn: 0.04 % of the truth, and the guard refused a correct run at "10 % of
    # gross". The fix agreed with the one shape it had been tested on. See D-093.
    gross = (sum(abs(deltas.get(name, 0.0)) for name in STATE_RECEIPTS)
             + sum(abs(deltas.get(name, 0.0)) for name in STATE_TRANSFERS)
             + abs(employer_contribution_delta)
             + sum(abs(v) for v in aggregate_deltas.values()))
    scale = max(abs(reform_cost), abs(expected_cost), floor)
    allowed = max(rtol * scale, gross_rtol * gross)
    if abs(unexplained) > allowed:
        raise SectorBalanceError(
            f"le coût annoncé ne correspond pas à ce que les instruments ont bougé : "
            f"coût rapporté {reform_cost:+,.0f} EUR contre {expected_cost:+,.0f} EUR "
            f"reconstitué depuis les postes (prélèvements {receipts:+,.0f}, "
            f"transferts {transfers:+,.0f}, cotisations patronales "
            f"{employer_contribution_delta:+,.0f}, agrégats {aggregate:+,.0f}), "
            f"soit un écart de "
            f"{unexplained:+,.0f} EUR — {unexplained / scale:+.2%} du net et "
            f"{unexplained / gross if gross else 0:+.3%} du brut ({gross:+,.0f} EUR). "
            f"Un secteur a bougé sans entrer dans le coût, ou l'inverse."
        )
    return {
        "reform_cost": reform_cost,
        "expected_cost": expected_cost,
        "state_gain": state_gain,
        "aggregate": aggregate,
        "unexplained": unexplained,
    }


#: The firm instruments whose sum IS the total. `prelevements_entreprise` is computed
#: by an OpenFisca formula; adding these up here is a second, independent route to the
#: same number, so an instrument added to one and not the other breaks the identity.
FIRM_COMPONENTS = (
    "impot_societes", "contribution_sociale_is", "cebge", "cvae", "c3s",
)


def firm_balance(
    deltas: dict[str, float],
    *,
    reform_cost: float,
    rtol: float = BALANCE_RTOL,
    gross_rtol: float = FIRM_BALANCE_GROSS_RTOL,
    floor: float = BALANCE_FLOOR_EUR,
) -> dict[str, float]:
    """Assert a firm reform's cost equals the sum of the instruments that moved.

    Carries the same gross-scaled allowance as `sector_balance`, for the same reason: a
    firm reform that raises one instrument to pay for cutting another has a near-zero net
    and billions of gross, and the net is not a measure of its size (D-093).

    The firm side has no household term, so the double entry is between the total the
    engine computes and the components this guard adds. A new instrument wired into
    `prelevements_entreprise` but not into the reported set — or the reverse — shows up
    here rather than as a quietly wrong headline.
    """
    components = sum(deltas.get(name, 0.0) for name in FIRM_COMPONENTS)
    expected_cost = -components
    unexplained = reform_cost - expected_cost
    gross = sum(abs(deltas.get(name, 0.0)) for name in FIRM_COMPONENTS)
    scale = max(abs(reform_cost), abs(expected_cost), floor)
    allowed = max(rtol * scale, gross_rtol * gross)
    if abs(unexplained) > allowed:
        missing = {
            name: value for name, value in deltas.items()
            if name not in FIRM_COMPONENTS and abs(value) > floor
        }
        raise SectorBalanceError(
            f"le coût annoncé de la réforme entreprises ne correspond pas à la somme "
            f"des instruments : {reform_cost:+,.0f} EUR contre {expected_cost:+,.0f} "
            f"reconstitué, écart {unexplained:+,.0f} EUR "
            f"({unexplained / scale:+.2%}). Postes hors périmètre ayant bougé : "
            f"{sorted(missing) or 'aucun'}."
        )
    return {
        "reform_cost": reform_cost,
        "expected_cost": expected_cost,
        "unexplained": unexplained,
    }
