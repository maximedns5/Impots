"""ERFS interrupt E2 — the validation scorecard, PRE-REGISTERED before any ERFS number.

**Nothing in this file was chosen after seeing an ERFS figure.** It is committed first, on
purpose: a tolerance picked once the residual is known is not a tolerance, it is a
description of the residual wearing a verdict's clothes. `verify_tolerance_unchanged` in
`preregistration` already makes this enforceable — the integrity lives in git history, not
in the file, so widening a band after the fact leaves a trace that a re-read of the file
cannot hide.

WHY ERFS IS WORTH SPENDING NOTHING ON. Every other comparator this project holds has been
spent: the wage bill is calibrated, the household-type margins are raked, DGFiP n° 41's
fractiles were spent by L1's rake. ERFS is **independent of all of them** — the synthetic
population was never fitted to it, not once, on any axis. That makes a verdict against ERFS
a real verdict, and it is why E3 is «nothing»: the moment any of this is used to
recalibrate, it stops being evidence and becomes a target, exactly as n° 41 did.

**L1's spent-source refusal therefore does NOT apply here.** `Line.raked_top_tail` refuses a
verdict because the population was fitted to that comparator. It was never fitted to ERFS.

THE AXES, AND WHY EACH ONE IS ONE THE POPULATION WAS NEVER CALIBRATED TO.

* **A1 — decile shares of income.** Raking hit household-type and person margins, never the
  shape of the income distribution. D-074 measured the sampler; nothing ever fitted the
  deciles themselves.
* **A2 — composition × income.** The two margins were raked SEPARATELY. Their JOINT is
  unconstrained, and a population can hit both margins while getting their cross badly
  wrong — which is exactly the failure a marginal-only calibration cannot see.
* **A3 — prestations eligibility mass.** The reconciliation lines compare SPEND against a
  take-up bridge. Eligibility COUNT is a different quantity, and no calibration touched it.
* **A4 — the capital-income joint.** This is the F1b gate re-examined, and its expected
  result is known in advance and structural rather than statistical.

WHAT IS PRE-REGISTERED AS EXPECTED TO FAIL, so that failing is not a surprise anyone can
later present as a discovery:

1. **A4 fails by construction.** The synthetic population carries identically zero capital
   income — `revenus_nets_du_capital` is 0,00 everywhere, as the reconciliation report
   states on three separate lines. Any capital axis therefore scores 100 % short, and the
   informative question is not whether it fails but WHAT SHARE of ERFS households hold
   capital income at all, which is the number F1b needed and never had.
2. **The top millième is uninformative in BOTH directions.** Our tail was thin (−64,3 %
   before L1's rake) and **ERFS's own top tail undercounts** — a survey cannot see the very
   top, which is why DGFiP n° 41 exists. Comparing two undercounts measures neither, so the
   top centile carries NO PASS/FAIL, by pre-registration rather than by later excuse.
3. **The bottom decile is fragile too**, for the opposite reason: near-zero and negative
   incomes make relative residuals explode on denominators that approach zero — the first
   standing question, and the reason n° 41 publishes «n.s.» there itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: The vintage rule, pre-registered by the 2026-09-17 addendum and restated here because a
#: rule that lives only in a review file is one an implementer can miss: the engine runs AT
#: 2022 against ERFS 2022. Never ERFS aged forward onto the 2024 base — that would compare a
#: mechanically uprated population with an observed one and call the ageing error a model
#: error.
VINTAGE = 2022

#: The FPR delivery has two tables and no foyer table. Foyer-level checks exist only where
#: the dictionary supports the mapping, and an axis that needs one it cannot build is
#: REFUSED rather than approximated.
TABLES = ("menage", "individu")

Band = Literal["informative", "no_verdict"]


@dataclass(frozen=True)
class Axis:
    """One validation axis, with its tolerance fixed before the first measurement."""

    key: str
    label: str
    tolerance: float
    """Relative, on the axis's own statistic. Fixed here, before any ERFS number."""
    rationale: str
    """WHY this number and not a rounder one. A tolerance without a reason is a number
    somebody will widen."""
    expected: str = ""
    """What is expected to happen, recorded in advance so that a predicted failure cannot
    later be presented as a discovery."""
    band: Band = "informative"


#: The scorecard. Tolerances are deliberately TIGHT ENOUGH TO FAIL — the handoff's rule is
#: that a scorecard admitting everything measures nothing, and the fastest way to build one
#: that admits everything is to pick round, comfortable numbers.
AXES: tuple[Axis, ...] = (
    Axis(key="a1_decile_shares",
         label="Parts du revenu disponible par décile (déciles 2 à 9)",
         tolerance=0.10,
         rationale=(
             "10 % relatif par décile. La réconciliation mesure déjà les déciles 5 à 9 à "
             "+3,6 % à +9,2 % contre Filosofi — un comparateur DIFFÉRENT, non dépensé "
             "ici. Une bande à 10 % laisse donc passer ce qui est déjà connu et refuse ce "
             "qui serait pire ; à 20 % elle n'aurait rien pu refuser."),
         expected="Les déciles du milieu devraient passer ; les extrêmes sont hors verdict."),
    Axis(key="a1_decile_tails",
         label="Premier décile et dernier centile",
         tolerance=0.0,
         rationale=(
             "Aucun verdict. En bas, des revenus proches de zéro ou négatifs font exploser "
             "tout résidu relatif — première question permanente, et la raison pour "
             "laquelle la DGFiP publie elle-même « n.s. » sur ce décile. En haut, NOS "
             "deux sources sous-comptent : notre queue l'était de 64,3 % avant le recalage "
             "L1, et l'ERFS sous-compte la sienne parce qu'une enquête ne voit pas le "
             "sommet. Comparer deux sous-comptages ne mesure ni l'un ni l'autre."),
         expected="Aucun verdict rendu, par préenregistrement et non par excuse a posteriori.",
         band="no_verdict"),
    Axis(key="a2_composition_income",
         label="Composition du ménage × quartile de revenu (le JOINT)",
         tolerance=0.15,
         rationale=(
             "15 % relatif sur la part de chaque type de ménage dans chaque quartile. Le "
             "raking a atteint les marges type-de-ménage ET personne SÉPARÉMENT : leur "
             "JOINT n'est contraint par rien. C'est l'axe où une calibration par marges "
             "peut être exacte et fausse à la fois, donc la bande est plus large que A1 "
             "(une case croisée porte moins d'effectif) mais reste refusante."),
         expected="Inconnu. C'est l'axe le plus informatif du tableau."),
    Axis(key="a3_prestations_mass",
         label="Masse d'éligibilité aux prestations (effectif, pas dépense)",
         tolerance=0.20,
         rationale=(
             "20 % relatif sur l'EFFECTIF éligible. Les lignes de réconciliation comparent "
             "une DÉPENSE à travers un pont de non-recours ; l'effectif éligible est une "
             "autre grandeur, qu'aucune calibration n'a touchée. La bande est large parce "
             "que l'éligibilité dépend de règles que l'ERFS ne porte pas toutes — mais "
             "elle refuse encore : D-015 mesurait une erreur de densité de +107 %."),
         expected="Écart attendu, direction inconnue ; les trois lignes prestations sont "
                  "rouges depuis la phase 1."),
    Axis(key="a4_capital_joint",
         label="Revenus du capital : présence et jointure avec le revenu",
         tolerance=0.0,
         rationale=(
             "Aucune tolérance parce qu'aucune comparaison n'est possible : la population "
             "synthétique porte identiquement ZÉRO revenu du capital — "
             "`revenus_nets_du_capital` vaut 0,00, comme f2dc, f2tr, f4ba, les plus-values "
             "et le PFU. Un résidu de −100 % n'est pas une mesure, c'est une absence."),
         expected=(
             "Échec par construction. Ce que cet axe doit RENDRE est la grandeur que le "
             "gate F1b n'avait pas : quelle PART des ménages ERFS porte un revenu du "
             "capital, et comment il se joint au revenu. C'est un constat, pas un verdict."),
         band="no_verdict"),
)


def axis(key: str) -> Axis:
    for entry in AXES:
        if entry.key == key:
            return entry
    raise KeyError(key)


def verdict_axes() -> tuple[Axis, ...]:
    """Axes that actually render a pass/fail. The others are findings, not verdicts."""
    return tuple(a for a in AXES if a.band == "informative")
