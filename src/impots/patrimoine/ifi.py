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

from impots.parameters import update_existing

#: The IFI forfait's parameter path, and the date the correction is written from.
FORFAIT_PATH = ("taxation_capital", "impot_fortune_immobiliere_ifi_partir_2018",
                "forfait_mobilier", "majoration_forfaitaire")

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
        return {code: getattr(self, name) for name, code in CASES.items()}


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
    """The tax-benefit system to price with, corrected unless asked otherwise."""
    from impots.engine.system import baseline

    if forfait_mobilier:
        return baseline()

    from openfisca_core.reforms import Reform

    instant = f"{year}-01-01"

    class NoForfaitMobilier(Reform):
        name = "IFI sans forfait mobilier (CGI art. 965)"

        def apply(self) -> None:
            def modify(parameters: Any) -> Any:
                # update_existing, not a bare update: D-044's rule. Writing a
                # parameter the year's formula does not read would read back fine and
                # change nothing, which is the failure this project has met four times.
                update_existing(parameters, FORFAIT_PATH, start=instant, value=0.0,
                                instant=instant)
                return parameters

            self.modify_parameters(modifier_function=modify)

    return NoForfaitMobilier(baseline())


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

    # THE SEUIL D'ASSUJETTISSEMENT, which openfisca does not apply.
    #
    # CGI art. 964: the IFI is owed by those whose net taxable real-estate wealth
    # EXCEEDS 1 300 000 EUR. Below that there is no tax at all. `isf_ifi_iai` for 2018+
    # is `bareme.calc(assiette)` with no eligibility test, so the engine charges the
    # 0,5 % bracket to everyone from 800 000 upward: measured, 500 EUR at 900 000 and
    # 2 500 EUR at 1 299 999.
    #
    # The tell that this is a defect rather than a reading is that it makes the tax
    # NON-MONOTONIC — 1 299 999 pays 2 500 EUR and 1 300 000 pays 1 250 EUR, because
    # the décote starts only at the threshold. A tax that falls as the base rises is
    # not a policy anyone wrote.
    #
    # Unlike the forfait mobilier this is not contested: art. 964 is explicit, and the
    # 1989-2017 formula did carry a gate (though `bareme.rates[1]`, comparing a base in
    # euros against a RATE of 0,007, which is always true — so that gate never worked
    # either). The threshold is READ from the tree rather than written here: it is the
    # décote's own lower bound, which is the same 1 300 000 by construction.
    threshold = _liability_threshold(system, year)
    if values["assiette_isf_ifi"] <= threshold:
        for name in ("isf_ifi_iai", "decote_isf_ifi", "isf_ifi_avant_plaf",
                     "isf_ifi_apres_plaf", "isf_ifi"):
            values[name] = 0.0

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
