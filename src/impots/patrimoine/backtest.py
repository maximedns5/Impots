"""The ISF-2017 backtest — Phase 5's out-of-sample test.

Every other check in this module compares the engine against data the cells were read
from. This one does not: the ISF ended in 2017, the figures below were published in 2023
from tax records this project has never touched, and nothing here was tuned to them. It
is the only genuinely out-of-sample number the wealth module has.

THE SOURCE. IPP Rapport n° 46 (octobre 2023), «Le plafonnement de l'impôt sur la
fortune», built on ISF-IFI and POTE via CASD and published as aggregates. Two tables
matter and they are not interchangeable:

  * **Table 1.1** gives redevable COUNTS by tranche — 356 229 in total, 257 729 /
    91 426 / 6 639 / 437 — and then, for every money column, only the SHARE
    attributable to capped households. It carries no ISF amount and no base per tranche.
    The brief expected per-tranche ISF here; it is not there.
  * **Table 1.2** gives the LEVELS, split by capped status rather than by tranche. That
    is what makes a backtest possible at all.

VINTAGES, stated because the rule binds and the report states them itself: 2017
declarations, 2016 reference income. Our simulation runs at period 2017, which is the
declaration year — so the wealth is at 1 January 2017 and the income underlying the
plafonnement is 2016, exactly as the report describes.

WHAT IS COMPARED. Table 1.2's mean household is reconstructed asset by asset — its
components sum to the published total to the decimal, in both groups, which is the check
that the reading is right — and priced through the engine's own ISF chain at 2017.

  capped group, pre-plafonnement    152 725 EUR against 153 417 published   **-0.5 %**
  capped group, post-plafonnement    53 987 EUR against  49 483 published    +9.1 %
  non-capped group                   30 918 EUR against  25 821 published   **+19.7 %**

**The -0,5 % is partly two errors cancelling, and saying so is the point.** Two known
biases run in opposite directions and neither is modelled:

  * **Jensen.** A mean household priced through a convex barème understates the mean tax,
    because E[f(W)] >= f(E[W]). This pushes our figure DOWN.
  * **The ISF réductions.** ISF-PME (up to 45 000 EUR) and dons at 75 % reduced the tax
    actually paid, and the published "ISF avant plafonnement" is net of them while we
    declare none. This pushes our figure UP.

The non-capped group at +19,7 % is where the second dominates: its estates are a third
the size, so a réduction of a few thousand euros is a large share of a 25 821 EUR tax. On
the capped group the two roughly offset. A backtest that lands at half a per cent because
two unmodelled effects cancel is not the same as one that lands there because everything
is right, and this module does not claim the second.

THE +9.1 % ON THE CAP IS EXPLAINED MECHANICALLY, and checked rather than asserted, per
the standing rule that a mechanical account comes before an economic one. The
plafonnement caps ISF-plus-income-taxes at 75 % of income, so it depends on the whole tax
side. Our representative household is SALARY-ONLY — the report publishes income
aggregates, not a composition we could reproduce — so it generates 34 893 EUR of
plafonnement-relevant tax against the published 51 154 (IR 32 486 plus prélèvements
sociaux 18 668). Missing social levies on capital income make the cap bite less, and a
cap that bites less leaves more tax standing.

What the cap does reproduce is its SHAPE: -64,7 % of pre-cap tax against a published
-67,7 %, on a mechanism worth two thirds of the bill.

TWO FINDINGS FELL OUT OF BUILDING IT, both recorded in D-090: the engine counts declared
furniture twice whenever the financial base is live, and the mapping of "titres avec
contrôle" decides the answer — sending it to `b1cb`, which carries a 75 % exoneration
the report's own post-abattement total does not apply, turns -0.5 % into -10.7 %.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Thousands, as the report prints them.
K = 1_000.0

#: Table 1.1, page index 22: ISF 2017 redevables by tranche of taxable wealth. Counts
#: only — every other column in that table is a SHARE attributable to capped households.
TRANCHE_COUNTS_2017 = {
    "1,3–2,57 M€": 257_729,
    "2,57–10 M€": 91_426,
    "10–50 M€": 6_639,
    "> 50 M€": 437,
}
#: The published total. The four tranche counts sum to 356 231 — two more — which is
#: rounding inside the publication, recorded rather than reconciled away.
TOTAL_REDEVABLES_2017 = 356_229

#: Table 1.1: the share of each tranche that is capped. The headline of the report.
CAPPED_SHARE_2017 = {
    "1,3–2,57 M€": 0.57, "2,57–10 M€": 6.25, "10–50 M€": 56.95, "> 50 M€": 72.54,
}


@dataclass(frozen=True)
class PublishedGroup:
    """One column of Table 1.2 — the mean household of a plafonnement status."""

    label: str
    residence_principale: float
    autres_immobiliers: float
    liquidites: float
    titres_cotes: float
    titres_avec_controle: float
    autres_biens_mobiliers: float
    dette: float
    """Negative, as printed."""
    patrimoine_taxable_pre_abattements: float
    patrimoine_taxable_post_abattements: float
    revenu_fiscal_reference: float
    impot_revenu: float
    prelevements_sociaux: float
    isf_avant_plafonnement: float
    isf_apres_plafonnement: float

    def components_sum(self) -> float:
        return (self.residence_principale + self.autres_immobiliers + self.liquidites
                + self.titres_cotes + self.titres_avec_controle
                + self.autres_biens_mobiliers + self.dette)

    def cases(self) -> dict[str, float]:
        """The 2042-ISF cases this household declares.

        `titres_avec_controle` goes to **b1ce**, with the rest of the securities, and not
        to b1cb. b1cb applies `taux_actions_conservees_6_ans` — 0,25, i.e. the 75 %
        exoneration for shares under an engagement de conservation — and the report's own
        post-abattement total does not apply any such exoneration: its pre- and
        post-abattement figures differ by 647 k EUR on a 13 929 k EUR estate, which is
        the résidence-principale abattement and little else. Routing them through b1cb
        would exempt 1 045 k EUR the report plainly still counts, and it moves the result
        from -0,5 % to -10,7 %.
        """
        return {
            "b1ab": self.residence_principale,
            "b1ac": self.autres_immobiliers,
            "b1cf": self.liquidites,
            "b1ce": self.titres_cotes + self.titres_avec_controle,
            "b1cg": self.autres_biens_mobiliers,
            "b2gh": -self.dette,
        }


#: Table 1.2, page index 24, in euros. Read from the file; the components sum to the
#: printed pre-abattement total exactly in both groups, which is the reading's own check.
PLAFONNES = PublishedGroup(
    label="plafonnés",
    residence_principale=978.1 * K, autres_immobiliers=1_736.5 * K,
    liquidites=4_677.1 * K, titres_cotes=4_191.6 * K,
    titres_avec_controle=1_393.6 * K, autres_biens_mobiliers=1_810.7 * K,
    dette=-858.5 * K,
    patrimoine_taxable_pre_abattements=13_929.1 * K,
    patrimoine_taxable_post_abattements=13_281.8 * K,
    revenu_fiscal_reference=130_812.0, impot_revenu=32_486.5,
    prelevements_sociaux=18_667.7,
    isf_avant_plafonnement=153_416.6, isf_apres_plafonnement=49_482.9,
)

NON_PLAFONNES = PublishedGroup(
    label="non-plafonnés",
    residence_principale=681.8 * K, autres_immobiliers=1_217.2 * K,
    liquidites=1_196.5 * K, titres_cotes=1_243.0 * K,
    titres_avec_controle=328.9 * K, autres_biens_mobiliers=434.0 * K,
    dette=-374.1 * K,
    patrimoine_taxable_pre_abattements=4_727.3 * K,
    patrimoine_taxable_post_abattements=4_473.1 * K,
    revenu_fiscal_reference=311_399.6, impot_revenu=79_973.3,
    prelevements_sociaux=35_979.6,
    isf_avant_plafonnement=25_820.9, isf_apres_plafonnement=25_820.9,
)

GROUPS = (PLAFONNES, NON_PLAFONNES)

#: Declared tolerance on the pre-plafonnement comparison. Reasoned rather than chosen: a
#: mean household priced through a convex barème understates the mean tax, and the ISF
#: réductions we do not model overstate it, so a few per cent is the best this design can
#: claim even when everything is right.
#:
#: ONE GROUP PASSES IT AND ONE DOES NOT, and both facts are pinned. The tolerance was NOT
#: widened to take the non-capped group in: a backtest that admits everything measures
#: nothing, and +19,7 % with a named cause is more useful than a tolerance stretched to
#: swallow it.
TOLERANCE_PRE_PLAFONNEMENT = 0.05


@dataclass(frozen=True)
class BacktestResult:
    group: PublishedGroup
    assiette: float
    avant_plafonnement: float
    apres_plafonnement: float

    @property
    def residual_avant(self) -> float:
        return self.avant_plafonnement / self.group.isf_avant_plafonnement - 1

    @property
    def residual_apres(self) -> float:
        return self.apres_plafonnement / self.group.isf_apres_plafonnement - 1

    @property
    def plafonnement_effect(self) -> float:
        """Our own cap, as a fraction of pre-cap tax."""
        if not self.avant_plafonnement:
            return 0.0
        return self.apres_plafonnement / self.avant_plafonnement - 1

    @property
    def published_plafonnement_effect(self) -> float:
        return (self.group.isf_apres_plafonnement
                / self.group.isf_avant_plafonnement - 1)


def run(group: PublishedGroup, year: int = 2017) -> BacktestResult:
    """Price one published group's mean household through the engine's ISF chain."""
    from openfisca_core.simulations import SimulationBuilder

    from impots.engine.system import baseline

    period = str(year)
    situation = {
        "individus": {"M": {"salaire_imposable": {period: group.revenu_fiscal_reference}}},
        "familles": {"f": {"parents": ["M"]}},
        "foyers_fiscaux": {"ff": {
            "declarants": ["M"],
            **{case: {period: value} for case, value in group.cases().items()},
        }},
        "menages": {"m": {"personne_de_reference": ["M"]}},
    }
    simulation = SimulationBuilder().build_from_entities(baseline(), situation)
    read = lambda name: float(simulation.calculate(name, period)[0])  # noqa: E731
    return BacktestResult(
        group=group,
        assiette=read("assiette_isf_ifi"),
        avant_plafonnement=read("isf_ifi_avant_plaf"),
        apres_plafonnement=read("isf_ifi_apres_plaf"),
    )


def run_all(year: int = 2017) -> list[BacktestResult]:
    return [run(group, year) for group in GROUPS]
