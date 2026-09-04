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
