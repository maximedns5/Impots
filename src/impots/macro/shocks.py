"""B1 — shock construction (PHASE4_SPEC §1).

Turns what the lower layers measured into a dated net fiscal impulse, labelled by
instrument, with the product allocation B2 needs to give it a shape.

**No propensity to consume appears here, and that is not an omission.** §1's sketch
routes household income deltas through an MPC to get a consumption impulse. That step
would double-count: Mésange's income-tax multiplier is the GDP response to an
income-tax cut, and the household decision to spend rather than save is already inside
it. B1 therefore stops at the fiscal impulse per instrument and lets the multiplier do
the rest — which is also why `mpc_by_income_position` dying (D-052) costs less than it
appeared to. It cost the decile differentiation, not the channel.

**The double-entry rule extends here** (D-045): the instrument impulses must add back to
the reform's own net cost. A shock that does not balance is not a smaller shock, it is a
mis-specified one, and `assert_balanced` refuses it.

**Instruments without a multiplier are refused, not approximated.** The mapping below is
deliberately partial, and the gaps are the interesting part.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

import numpy as np

from impots.macro import mesange
from impots.macro.tes import Tes

#: OpenFisca delta names to Mésange variants. Sign convention: a POSITIVE impulse is
#: expansionary — money moving towards households or firms — matching the convention
#: `mesange` puts every variant into.
#:
#: `crds` rides with `csg` because it is the same instrument in every respect that
#: matters to a macro model: a proportional levy on the same base, collected together.
#: That is a judgement, and it is here rather than buried so it can be argued with.
#: Knobs whose reforms are CONCENTRATED ON LOW WAGES, and which must therefore route
#: employer contributions to the targeted variant rather than the uniform one.
#:
#: This is the defect the adversarial pass called the most exploitable, and it is
#: specific to this project: the whole allègements-généraux work of Phase 3 moves these
#: knobs, and the uniform variant would have understated its employment effect by 39 %
#: at three years (290 000 against 403 000) because a uniform cut lands 80 % on
#: qualified workers while an allègement between 1 and 1.6 SMIC lands 44 % on
#: unqualified ones, whose labour demand is more elastic.
TARGETED_EMPLOYER_KNOBS = (
    "allegement_general_*", "bandeau_maladie_*", "bandeau_famille_*",
)

INSTRUMENT_MAP = {
    "ir": "impot_sur_le_revenu",
    "csg_imposable": "csg",
    "csg_deductible": "csg",
    "crds": "csg",
    "cotisations_salariales": "cotisations_salaries",
    "employer_contributions": "cotisations_employeurs",
}

#: Deltas that reach B1 with NO multiplier, and why. Each entry kills the macro path for
#: reforms that move only that instrument — visibly, with this text, rather than by
#: quietly borrowing a neighbouring variant.
UNMAPPED = {
    "af": "transfert",
    "ppa": "transfert",
    "rsa": "transfert",
    "aide_logement": "transfert",
    # The rest of `guards.STATE_TRANSFERS` (D-218): the prime de Noël, the complément
    # familial, the ASF, and the CRDS netted off the benefits, which belongs with them.
    "aefa": "transfert",
    "cf": "transfert",
    "asf": "transfert",
    "crds_pfam": "transfert",
    "crds_logement": "transfert",
    "crds_mini": "transfert",
    "impot_societes": "fiscalité des entreprises",
    "contribution_sociale_is": "fiscalité des entreprises",
    "cebge": "fiscalité des entreprises",
    "cvae": "fiscalité des entreprises",
    "c3s": "fiscalité des entreprises",
}

UNMAPPED_REASONS = {
    "transfert": (
        "Mésange ne publie pas de variante de transfert. La variante « dépense publique "
        "générique » en contient, mais c'est un COMPOSITE dont la page 106 donne la "
        "composition exacte : 8 % investissement public, 25 % rémunérations publiques, "
        "9 % prestations en nature, 12 % consommations intermédiaires et 46 % "
        "prestations sociales en espèces — et le document dit que ces composantes se "
        "transmettent à des vitesses différentes. L'emprunter surestimerait : les "
        "méta-analyses IMK donnent 0,39 (WP117) et 0,54 (WP139) pour les transferts "
        "contre 1,01 et 0,90 pour la dépense, soit un facteur deux à trois. Un canal "
        "qui meurt vaut mieux qu'un canal qui se trompe d'un facteur deux."
    ),
    "fiscalité des entreprises": (
        "Aucune variante d'impôt sur les sociétés en section 4. Les instruments "
        "entreprises ne doivent PAS hériter du multiplicateur des cotisations "
        "employeurs : celui-ci passe par le coût du travail, celui-là par le coût du "
        "capital, et le modèle ne mesure que le premier."
    ),
}

#: Which published final-use column gives each instrument's product allocation. The
#: national-accounts bridge §1 asks for is the accounts' own consumption vector: the
#: TES already publishes household final consumption by product, so no separate
#: COICOP→NAF crosswalk is introduced. One bridge, and stated, exactly as §1 provided
#: for when the decile differentiation died.
ALLOCATION_BASIS = {
    "impot_sur_le_revenu": "consommation_finale_menages",
    "cotisations_employeurs_ciblees": "fbcf",
    "csg": "consommation_finale_menages",
    "cotisations_salaries": "consommation_finale_menages",
    "cotisations_employeurs": "fbcf",
    "investissement_public": "fbcf",
    "depense_publique": "consommation_finale_apu",
    "tva": "consommation_finale_menages",
    "taxe_carbone": "consommation_finale_menages",
}

#: A reform under this size has no macro layer: its impulse is below the resolution of
#: every parameter the layer would apply to it.
MINIMUM_IMPULSE_EUR = 1.0e8

#: Double entry closes to this. Looser than the household guard's 1e-3 because the
#: instrument mapping legitimately drops nothing but rounds through float32 aggregates.
BALANCE_RTOL = 1e-3


class ShockError(RuntimeError):
    """A shock cannot be constructed from what the lower layers reported."""


@dataclass(frozen=True)
class Impulse:
    """A dated net fiscal impulse, labelled by instrument."""

    year: int
    by_instrument: dict[str, float]
    """Euros, expansionary-positive, keyed by Mésange variant."""
    unmapped: dict[str, float] = field(default_factory=dict)
    """Deltas with no multiplier. Not dropped — carried, so the caller must decide
    whether to report a partial macro path or refuse one."""
    net_fiscal_eur: float = 0.0

    @property
    def total(self) -> float:
        return sum(self.by_instrument.values())

    @property
    def unmapped_total(self) -> float:
        return sum(self.unmapped.values())

    @property
    def covered_share(self) -> float:
        """Share of the reform's movement that has a multiplier at all.

        GROSS magnitudes on both sides, never the signed totals: a benefit rise and a
        corporate tax cut are two uncovered instruments, and letting them cancel in the
        denominator would report a reform as better covered the more of it is missing.
        """
        mapped = sum(abs(v) for v in self.by_instrument.values())
        missing = sum(abs(v) for v in self.unmapped.values())
        moved = mapped + missing
        return mapped / moved if moved > 0 else 0.0

    def reasons(self) -> dict[str, str]:
        return {
            name: UNMAPPED_REASONS[UNMAPPED[name]]
            for name in self.unmapped
            if name in UNMAPPED
        }


def targets_low_wages(knobs: tuple[str, ...] | None) -> bool:
    """Whether this reform's knobs concentrate on low wages.

    Decided from the KNOBS the reform moved, not from its deltas: the population layer
    reports one employer-contribution total either way, so the delta cannot tell a
    uniform rate cut from an allègement.
    """
    return any(
        fnmatch.fnmatch(knob, pattern)
        for knob in (knobs or ())
        for pattern in TARGETED_EMPLOYER_KNOBS
    )


def instrument_deltas(deltas: dict[str, float], *,
                      employer_contribution_delta: float = 0.0) -> dict[str, float]:
    """The deltas `build` reads, out of everything the population layer reports.

    `aggregate.deltas` carries every total the runner reports: salaries, disposable
    income, and the components of the income tax (`ir_avant_niches`, `reductions`,
    `credits_impot`) beside `ir` itself. Handed to `build` whole, the first of those
    raised — which is how every reform's macro path came back unavailable on the real
    population (D-218). Counted, the components would double the shock. So this keeps
    exactly the instruments `guards.sector_balance` counts, in its convention:

    * the state's receipts (`guards.STATE_RECEIPTS`), receipts-positive as reported;
    * the transfers it pays (`guards.STATE_TRANSFERS`), whose positive delta means the
      state pays MORE — negated here into the receipts-positive convention `build` reads;
    * the employer contributions actually paid, net of allègements, under the name
      `INSTRUMENT_MAP` gives them. `cotisations_employeur` is gross of the allègements
      and does not move when one changes (`aggregate._employer_contribution_delta`).
    """
    from impots.guards import STATE_RECEIPTS, STATE_TRANSFERS

    out = {name: deltas[name] for name in STATE_RECEIPTS if deltas.get(name)}
    out.update({name: -deltas[name] for name in STATE_TRANSFERS if deltas.get(name)})
    if employer_contribution_delta:
        out["employer_contributions"] = employer_contribution_delta
    return out


def build(deltas: dict[str, float], *, year: int,
          reform_cost: float | None = None,
          knobs: tuple[str, ...] | None = None) -> Impulse:
    """Map lower-layer deltas onto instrument impulses.

    `deltas` are receipts-positive as the population layer reports them — a tax rise is
    a positive delta — so each is negated into the expansionary convention. `knobs` are
    the reform's own knob names, needed only to tell a targeted employer-contribution
    reform from a uniform one, which the deltas cannot.
    """
    targeted = targets_low_wages(knobs)
    by_instrument: dict[str, float] = {}
    unmapped: dict[str, float] = {}
    for name, value in deltas.items():
        if value == 0.0:
            continue
        if name in INSTRUMENT_MAP:
            variant = INSTRUMENT_MAP[name]
            if variant == "cotisations_employeurs" and targeted:
                variant = "cotisations_employeurs_ciblees"
            by_instrument[variant] = by_instrument.get(variant, 0.0) - value
        elif name in UNMAPPED:
            unmapped[name] = -value
        else:
            raise ShockError(
                f"delta {name!r} is neither mapped to a multiplier nor listed as "
                f"unmapped. Add it to one or the other: silently ignoring it would "
                f"make the shock smaller than the reform without saying so."
            )
    unknown = set(by_instrument) - set(mesange.VARIANTS)
    if unknown:
        raise ShockError(f"instruments with no published variant: {sorted(unknown)}")
    return Impulse(year=year, by_instrument=by_instrument, unmapped=unmapped,
                   net_fiscal_eur=reform_cost if reform_cost is not None else 0.0)


def assert_balanced(impulse: Impulse, reform_cost: float, *,
                    rtol: float = BALANCE_RTOL) -> None:
    """Double entry (D-045): the impulse must add back to the reform's own cost.

    Compared on MAGNITUDE, not on a signed residual: for a cost, a larger miss reads as
    a smaller number, so a one-sided bound on the signed value passes exactly the cases
    it should fail. That mistake has been made once in this repository already.
    """
    constructed = impulse.total + impulse.unmapped_total
    expected = -reform_cost
    scale = max(abs(expected), MINIMUM_IMPULSE_EUR)
    residual = abs(constructed - expected)
    if residual / scale > rtol:
        raise ShockError(
            f"the constructed impulse ({constructed:,.0f} EUR) does not reconstitute "
            f"the reform's net cost ({expected:,.0f} EUR): off by {residual:,.0f}, "
            f"{residual / scale:.2%} of scale. An unbalanced shock is mis-specified, "
            f"not small."
        )


def allocation(tes: Tes, impulse: Impulse) -> np.ndarray:
    """Total final demand by product for this impulse, for B2 to compose.

    Each instrument is allocated on the published final-use column its money actually
    moves through, then the instruments are summed. An impulse whose instruments pull in
    opposite directions is refused rather than netted: netting would allocate the
    residual on a mix belonging to neither, and B2 cannot compose a negative demand.
    """
    if not impulse.by_instrument:
        raise ShockError("no mapped instrument: this reform has no macro path")
    signs = {np.sign(v) for v in impulse.by_instrument.values() if v != 0}
    if len(signs) > 1:
        raise ShockError(
            "instruments pull in opposite directions; compose each side separately, "
            "since a netted allocation would use a product mix belonging to neither"
        )
    total = np.zeros(tes.n)
    for variant, value in impulse.by_instrument.items():
        basis = ALLOCATION_BASIS.get(variant)
        if basis is None:
            raise ShockError(f"no allocation basis declared for {variant!r}")
        vector = (tes.final_uses[basis] + tes.imported_final_uses[basis]).clip(min=0.0)
        if vector.sum() <= 0:
            raise ShockError(f"allocation basis {basis!r} is empty")
        total += vector / vector.sum() * abs(value)
    return total
