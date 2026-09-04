"""Household IFI, priced through the engine's own ISF-IFI chain (Phase 5 M1).

The chain is openfisca's, not ours: `assiette_isf_ifi` → `isf_ifi_iai` (barème) →
`decote_isf_ifi` → `isf_ifi_avant_plaf` (dons, réduction PAC) → `isf_ifi_apres_plaf`
(plafonnement) → `isf_ifi`. Reusing it is the point — the décote window, the 75 %
plafonnement and the dons cap all come for free and stay correct as the tree is
updated. What this module adds is a 2042-IFI-shaped input, hand-derived goldens at
every kink, and one contested correction stated out loud.

TWO THINGS MEASURED HERE THAT NOBODY SHOULD REDISCOVER.

**1. Pricing IFI on a foyer with no income returns ZERO.** The plafonnement caps
IFI-plus-income-tax at 75 % of income; with no income the cap is nil, so the whole IFI
is abated. Measured: a 2 M EUR base gives 8 100 EUR of barème and 0 EUR of IFI at zero
salary, 8 100 EUR from 50 000 EUR of salary upward. Every golden in this module
therefore carries income, and a golden that did not would be the zero-masked
comparison the project spent an increment sweeping out — it would price nothing and
prove nothing.

**2. openfisca applies a 5 % forfait mobilier to the IFI base, and we switch it off.**
This is a CONTESTED reading, not a caught typo, and it is stated as such.

  * openfisca's case, written into the parameter's own documentation: CGI art. 973
    says IFI asset values follow the DMTG rules, and art. 764 I-3° puts a floor on
    meubles meublants at 5 % of the rest of the estate. The ISF file deliberately
    nulls its own forfait from 2018 and a new IFI one was created — so this was a
    decision, not a copy.
  * ours: art. 965 defines the IFI base as immovable property. Art. 973 governs how to
    VALUE what is in the base; art. 764's furniture floor values an asset class that
    the IFI base excludes entirely. Importing it taxes furniture through a tax whose
    base has no furniture in it.
  * the data, which is why this is not two lawyers arguing. Reconstructing the
    aggregate base from DGFiP's published per-tranche tax gives **-6.46 %** against
    the independently published aggregate without the forfait and **-10.92 %** with
    it. Every unmodelled relief — décote, plafonnement, dons — lowers tax and so
    pushes the reconstruction DOWN, which means the true figure is above both and the
    no-forfait reading is 4.46 points closer.

Evidence, not proof: a large enough relief could rescue the forfait. So it ships as
`forfait_mobilier=False` by DEFAULT with the switch kept, `openfisca_reading()` prices
the other one, and the difference is reportable rather than buried.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from impots.patrimoine import corrections

#: Re-exported for callers that used to import it from here; the correction itself
#: now lives in `patrimoine.corrections`, applied to the project's baseline.
FORFAIT_PATH = corrections.FORFAIT_PATH

#: The declaration cases this module fills, and what each one is.
#: Names are the 2042-IFI's own; the codes are what openfisca reads.
CASES = {
    "residence_principale": "b1ab",
    "autres_immeubles_batis": "b1ac",
    "bois_et_forets": "b1bc",
    "biens_ruraux_loues_long_terme": "b1be",
    "parts_groupements_forestiers_agricoles": "b1bh",
    "autres_biens_non_batis": "b1bk",
    "meubles_meublants_declares": "b1cg",
    "passif_deductible": "b2gh",
    "dons_organismes_interet_general": "b2nc",
    # ISF-only. Read at 2017, silently dropped at 2024 — see `patrimoine.regimes`.
    "droits_sociaux_conserves_six_ans": "b1cb",
    "droits_sociaux_non_exoneres": "b1cd",
    "valeurs_mobilieres": "b1ce",
    "liquidites": "b1cf",
}

#: The chain, in the order it computes. Reported whole because a reader who sees only
#: the last number cannot tell a décote from a plafonnement.
CHAIN = ("isf_ifi_imm_bati", "isf_ifi_imm_non_bati", "assiette_isf_ifi", "isf_ifi_iai",
         "decote_isf_ifi", "isf_ifi_avant_plaf", "isf_ifi_apres_plaf", "isf_ifi")


@dataclass(frozen=True)
class IfiInputs:
    """A 2042-IFI-shaped declaration, in euros."""

    residence_principale: float = 0.0
    """Gross value. The 30 % abattement is applied by the engine, not here."""
    autres_immeubles_batis: float = 0.0
    bois_et_forets: float = 0.0
    biens_ruraux_loues_long_terme: float = 0.0
    parts_groupements_forestiers_agricoles: float = 0.0
    autres_biens_non_batis: float = 0.0
    meubles_meublants_declares: float = 0.0
    passif_deductible: float = 0.0
    dons_organismes_interet_general: float = 0.0
    revenu_imposable: float = 0.0
    """NOT part of the IFI declaration, and required anyway: the plafonnement reads it,
    and at zero income it abates the whole tax. See the module docstring."""
    couple: bool = False
    enfants: int = 0

    def cases(self) -> dict[str, float]:
        """Only the fields this dataclass carries.

        `CASES` also maps the four ISF-only financial cases, which the wire model
        `schemas.Patrimoine` has and this one does not: `IfiInputs` describes an IFI
        declaration, and the IFI base has no financial wealth in it (CGI art. 965).
        Iterating `CASES` blindly asked for attributes that do not exist here — a real
        failure caught by a test, and the fix is to skip rather than to add fields that
        would misdescribe the tax.
        """
        return {code: getattr(self, name) for name, code in CASES.items()
                if hasattr(self, name)}


@dataclass
class IfiResult:
    """The whole chain, plus what each step took off."""

    inputs: IfiInputs
    year: int
    forfait_mobilier: bool
    values: dict[str, float] = field(default_factory=dict)

    @property
    def ifi(self) -> float:
        """The tax due, POSITIVE. openfisca stores taxes negative."""
        return -self.values["isf_ifi"]

    @property
    def assiette(self) -> float:
        return self.values["assiette_isf_ifi"]

    @property
    def decote(self) -> float:
        return self.values["decote_isf_ifi"]

    @property
    def abattu_par_plafonnement(self) -> float:
        return self.values["isf_ifi_avant_plaf"] - self.values["isf_ifi_apres_plaf"]


def _system(year: int, forfait_mobilier: bool) -> Any:
    """The tax-benefit system to price with.

    `baseline()` already carries BOTH corrections (see `patrimoine.corrections`), so the
    default path just uses it. Asking for the forfait means asking for openfisca's own
    reading, which is `uncorrected_baseline()` — the raw reference implementation, named
    out loud so nothing reaches for it by accident.
    """
    from impots.engine.system import baseline, uncorrected_baseline

    return uncorrected_baseline() if forfait_mobilier else baseline()


def price(inputs: IfiInputs, year: int = 2024, *,
          forfait_mobilier: bool = False) -> IfiResult:
    """Price one foyer's IFI, returning the whole chain.

    `forfait_mobilier=True` reproduces openfisca's own reading; the default is ours.
    """
    from openfisca_core.simulations import SimulationBuilder

    period = str(year)
    individus: dict[str, Any] = {
        "declarant": {"salaire_imposable": {period: inputs.revenu_imposable}}}
    declarants = ["declarant"]
    if inputs.couple:
        individus["conjoint"] = {"salaire_imposable": {period: 0.0}}
        declarants.append("conjoint")
    personnes_a_charge = [f"enfant{i}" for i in range(inputs.enfants)]
    for name in personnes_a_charge:
        individus[name] = {}

    situation = {
        "individus": individus,
        "familles": {"famille": {"parents": declarants, "enfants": personnes_a_charge}},
        "foyers_fiscaux": {"foyer": {
            "declarants": declarants, "personnes_a_charge": personnes_a_charge,
            **{code: {period: value} for code, value in inputs.cases().items()},
        }},
        "menages": {"menage": {
            "personne_de_reference": [declarants[0]],
            "conjoint": declarants[1:2],
            "enfants": personnes_a_charge,
        }},
    }
    system = _system(year, forfait_mobilier)
    simulation = SimulationBuilder().build_from_entities(system, situation)
    values = {name: float(simulation.calculate(name, period)[0]) for name in CHAIN}

    # The seuil gate is NOT applied here: it lives in `patrimoine.corrections`, on the
    # baseline system, so every path in the project sees the same IFI. Applying it here
    # too would be a second implementation of the same rule, and the two would drift.
    # `openfisca_reading()` deliberately does not get it, which is the point of it.

    return IfiResult(
        inputs=inputs, year=year, forfait_mobilier=forfait_mobilier, values=values,
    )


def _liability_threshold(system: Any, year: int) -> float:
    """1 300 000 EUR, read from the tree rather than written down here."""
    node = (system.get_parameters_at_instant(f"{year}-01-01")
            .taxation_capital.impot_fortune_immobiliere_ifi_partir_2018.decote)
    return float(node.borne_inferieure_decote)


def openfisca_reading(inputs: IfiInputs, year: int = 2024) -> IfiResult:
    """The same foyer priced with the 5 % forfait mobilier left in.

    Kept so the contested correction can be quantified on any household rather than
    argued about, and so a reader can see both numbers.
    """
    return price(inputs, year, forfait_mobilier=True)
