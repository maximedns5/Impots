"""Where this project's reading of the law differs from openfisca's, and why.

**A correction here is a serious act.** It means we compute something different from the
reference implementation, and every one of them is a place where we could be the ones who
are wrong. So the bar is: a legal citation, a measured demonstration of the difference, a
decision-log entry, and a KILL TEST that fails the day openfisca changes its mind — at
which point the correction must be removed rather than kept as decoration.

They are applied to `engine.system.baseline()`, so there is ONE IFI figure in this
codebase rather than a corrected one in the wealth module and a raw one on the wire.
Shipping an output row named `ifi` that we know to be wrong is not a thing to do.

**Blast radius, measured rather than asserted:** both corrections bite only on a foyer
that declares real-estate wealth, and nothing else in this project declares any — the
synthetic population carries no wealth, and every golden household is salary-only. So
`isf_ifi` was identically zero everywhere before this and the full suite is the proof.

---

**Correction 1 — the seuil d'assujettissement (CGI art. 964), D-079.**

The IFI is owed only by foyers whose net taxable real-estate wealth EXCEEDS 1 300 000
EUR. `isf_ifi_iai` for 2018+ is `bareme.calc(assiette)` with no eligibility test, so the
engine charges the 0,5 % bracket from 800 000 upward: measured, 500 EUR at 900 000 and
2 500 EUR at 1 299 999.

The proof that this is a defect and not a reading is that it makes the tax NON-MONOTONIC.
1 299 999 owes 2 500 EUR; 1 300 000 owes 1 250 EUR. Crossing the threshold halves the
tax, because the décote begins only at the threshold. A tax that falls as its base rises
is not a policy anyone wrote.

The 1989-2017 formula did carry a gate — `(assiette >= bareme.rates[1])` — but it
compares a base in euros against a RATE of 0,007, so it is always true and that gate never
worked either.

**Correction 2 — the 5 % forfait mobilier, D-079. CONTESTED, and labelled so.**

openfisca adds 5 % of the base as presumed furniture. Its parameter carries a real legal
argument: art. 973 defers IFI valuation to the DMTG rules, and art. 764 I-3° floors
meubles meublants at 5 % of the rest of an estate. The ISF file nulls its own forfait from
2018 and a fresh IFI one was created at 0,05 — this was a decision, not a copy.

Our reading: art. 965 puts only immovable property in the IFI base, so art. 764's
furniture floor has nothing in scope to value. Art. 973 says how to value what IS in the
base; it does not put furniture into it.

The published data discriminates, which is why this is not two readings arguing.
Reconstructing the aggregate base from DGFiP's per-tranche tax lands at -6,46 % against
the independently published aggregate without the forfait and -10,92 % with it; since
every unmodelled relief lowers tax and pushes the reconstruction down, the truth is above
both and the forfait is 4,46 points further from it.

That is evidence, not proof — a large enough relief would rescue it — which is why
`patrimoine.ifi.openfisca_reading()` still prices the other way and the difference
(+9,5 % of tax on a 2 M base) is reportable rather than buried.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

IFI_NODE = ("taxation_capital", "impot_fortune_immobiliere_ifi_partir_2018")
FORFAIT_PATH = (*IFI_NODE, "forfait_mobilier", "majoration_forfaitaire")


@dataclass(frozen=True)
class Correction:
    """One documented departure from openfisca, and how to know it is still needed."""

    name: str
    citation: str
    decision: str
    kill_test: str
    """The test that fails if openfisca fixes this, so the correction gets removed."""


CORRECTIONS: tuple[Correction, ...] = (
    Correction(
        name="ifi_seuil_assujettissement",
        citation="CGI art. 964 — l'IFI est dû au-delà de 1 300 000 EUR de patrimoine net",
        decision="D-079",
        kill_test="test_the_engine_alone_would_tax_below_the_threshold",
    ),
    Correction(
        name="isf_forfait_mobilier_double_compte",
        citation="CGI art. 764 I-3° — le forfait de 5 % est un PLANCHER, « la preuve "
                 "contraire étant aussi réservée » : la valeur déclarée REMPLACE la "
                 "présomption, elle ne s'y ajoute pas",
        decision="D-090",
        kill_test="test_the_engine_alone_counts_declared_furniture_twice",
    ),
    Correction(
        name="ifi_forfait_mobilier",
        citation="CGI art. 965 — la base de l'IFI est immobilière ; art. 764 I-3° "
                 "plancher les meubles meublants, qui n'y sont pas",
        decision="D-079",
        kill_test="test_the_forfait_mobilier_correction_is_switchable_and_quantified",
    ),
)


def apply_to(system: Any, *, year: int = 2024) -> Any:
    """Return `system` with our legal corrections applied.

    Uses a Reform, so the parameter tree is cloned and the system handed in is
    untouched — the same property `test_no_mutation` keeps us honest about elsewhere.
    """
    from openfisca_core.reforms import Reform

    from impots.parameters import update_existing

    instant = f"{year}-01-01"

    class LegalCorrections(Reform):
        name = "impots-legal-corrections:ifi"

        def apply(self) -> None:
            def modify(parameters: Any) -> Any:
                # update_existing, never a bare update: writing a parameter the year's
                # formula does not read would read back fine and change nothing, which
                # is the failure this project has met four times (D-044).
                update_existing(parameters, FORFAIT_PATH, start=instant, value=0.0,
                                instant=instant)
                return parameters

            self.modify_parameters(modifier_function=modify)
            self.update_variable(_gated_isf_ifi())
            self.update_variable(_assiette_without_double_count())

    return LegalCorrections(system)


def _gated_isf_ifi() -> Any:
    """`isf_ifi`, zeroed below the liability threshold.

    A formula replacement rather than a parameter write, because the missing gate is
    missing from the FORMULA — there is no parameter whose value could restore it. The
    threshold is READ from the tree (the décote's lower bound, the same 1 300 000 by
    construction) rather than written here, so a reform that moves it moves this too.
    """
    from openfisca_core.model_api import YEAR, Variable, min_
    from openfisca_france.entities import FoyerFiscal

    class isf_ifi(Variable):  # openfisca's naming convention, not ours
        value_type = float
        entity = FoyerFiscal
        label = "Montant d'ISF-IFI, nul sous le seuil d'assujettissement (CGI art. 964)"
        definition_period = YEAR
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000036377128"

        def formula(foyer_fiscal, period, parameters):
            b4rs = foyer_fiscal("b4rs", period)
            apres_plaf = foyer_fiscal("isf_ifi_apres_plaf", period)
            assiette = foyer_fiscal("assiette_isf_ifi", period)
            node = parameters(period).taxation_capital
            seuil = node.impot_fortune_immobiliere_ifi_partir_2018.decote.borne_inferieure_decote
            due = min_(-(apres_plaf - b4rs), 0)
            # Strictly above: art. 964 says "excède", and a foyer exactly at the
            # threshold owes nothing.
            return due * (assiette > seuil)

    return isf_ifi


def _assiette_without_double_count() -> Any:
    """`assiette_isf_ifi`, with declared furniture counted once instead of twice.

    THE DEFECT. `isf_droits_sociaux` sums `isf_actions_sal + b1cc + b1cd + b1ce + b1cf +
    b1cg` — it INCLUDES b1cg, the declared movable property. `assiette_isf_ifi` then adds
    `forf_mob = (b1cg != 0) * b1cg` on top of a total that already contains it. Measured
    at 2017: b1cg of 1 000 000 EUR produces an assiette of 2 000 000 EUR.

    THE LAW. Art. 764 I-3° floors meubles meublants at 5 % of the rest of the estate,
    «la preuve contraire étant aussi réservée» — so a taxpayer may declare their actual
    value INSTEAD of accepting the presumption. Declaring replaces the forfait; it does
    not stack with it. Being taxed twice for using a legal option is not a policy anyone
    wrote, and it penalises exactly the taxpayer who declares rather than presumes.

    WHY IT WAS INVISIBLE UNTIL NOW. `isf_droits_sociaux` carries `end = "2017-12-31"`, so
    at 2024 it returns zero, b1cg is not in the total, and adding it once is correct. The
    defect only appears where that variable is LIVE — at 2017, and at 2024 under our own
    ISF revival, which lifts the end date and brings the double count back with the
    financial base. Measured: the revived system gives 2 000 000 EUR for the same
    declaration the IFI prices at 1 000 000.

    The fix subtracts b1cg from the financial component only WHERE THAT COMPONENT IS
    LIVE, so IFI-2024 behaviour is unchanged to the euro — which the suite proves rather
    than this docstring asserting.
    """
    from openfisca_core.model_api import YEAR, Variable, max_, where
    from openfisca_france.entities import FoyerFiscal

    def _assiette(foyer_fiscal, period, node):
        """The shared arithmetic; only the parameter node differs by era."""
        bati = foyer_fiscal("isf_ifi_imm_bati", period)
        non_bati = foyer_fiscal("isf_ifi_imm_non_bati", period)
        droits_sociaux = foyer_fiscal("isf_droits_sociaux", period)
        b1cg = foyer_fiscal("b1cg", period)
        b2gh = foyer_fiscal("b2gh", period)
        # b1cg is inside droits_sociaux WHEN that variable is live. Remove it there, so
        # the declared value enters exactly once, through forf_mob below.
        financier = where(droits_sociaux > 0, max_(droits_sociaux - b1cg, 0),
                          droits_sociaux)
        total = bati + non_bati + financier
        forf_mob = ((b1cg != 0) * b1cg
                    + (b1cg == 0) * total * node.forfait_mobilier.majoration_forfaitaire)
        return total + forf_mob - b2gh

    class assiette_isf_ifi(Variable):
        value_type = float
        entity = FoyerFiscal
        label = "Assiette de l'ISF-IFI, mobilier déclaré compté une seule fois"
        definition_period = YEAR
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006310333"

        # Three dated variants, mirroring the engine's own: each era reads ITS OWN
        # parameter node. A single formula reading the IFI node raised
        # ParameterNotFoundError at 2017, which is the loud failure that caught it.
        def formula_2018_01_01(foyer_fiscal, period, parameters):
            node = parameters(period).taxation_capital.impot_fortune_immobiliere_ifi_partir_2018
            return _assiette(foyer_fiscal, period, node)

        def formula_1989_01_01(foyer_fiscal, period, parameters):
            node = parameters(period).taxation_capital.impot_solidarite_fortune_isf_1989_2017
            return _assiette(foyer_fiscal, period, node)

        def formula(foyer_fiscal, period, parameters):
            node = parameters(period).taxation_capital.impot_grandes_fortunes_1982_1986
            return _assiette(foyer_fiscal, period, node)

    return assiette_isf_ifi
