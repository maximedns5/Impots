"""French corporate taxation as vectorised formulas (PHASE2_SPEC §2).

Every rate, threshold and base lives in the dated YAML tree next door, never in
this file — so a backdated run and a reform are the same operation on the
parameter tree, exactly as on the household side.

## What is modelled, and the one thing that biases the answer

IS at the normal and reduced rates, the contribution sociale on IS, the CEBGE,
CVAE and C3S. Loss-making firms carry a `benefice_imposable` of zero and pay no
IS, which is how the population represents them (§3.3).

**There is no carry-forward of losses.** Deficits reduce a real firm's tax in
later years; ours cannot, because carry-forward needs firm panels that are not
open data. This biases simulated IS **upward**, mechanically, and the
reconciliation report says so rather than leaving the reader to discover it.

CFE is deliberately absent (§2.5): it depends on communal valeur locative and
thousands of local rates, and a plausible-looking fake would be worse than a
stated hole.
"""

from __future__ import annotations

import numpy as np
from openfisca_core.periods import YEAR
from openfisca_core.variables import Variable

from impots.entreprises.entities import Entreprise


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
class chiffre_affaires(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Chiffre d'affaires hors taxes"


class benefice_imposable(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Résultat fiscal imposable, plancher à zéro"
    documentation = """Fiscal result, not the accounting result: the two differ by
    reintegrations and deductions our data cannot see, and the population applies a
    published aggregate ratio between them. Loss-makers carry zero — there is no
    carry-forward (see the module docstring)."""


class valeur_ajoutee(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Valeur ajoutée servant d'assiette à la CVAE"
    documentation = """Proxied by accounting value added from ESANE. Fiscal value
    added for CVAE has its own definition and is capped as a share of turnover; the
    proxy is stated in the reconciliation report's method notes."""


class capital_libere_detenu_personnes_physiques(Variable):
    value_type = bool
    entity = Entreprise
    definition_period = YEAR
    default_value = True
    label = "Capital entièrement libéré et détenu à 75 % au moins par des personnes physiques"
    documentation = """A condition of the reduced IS rate that no open register
    records. Defaults to true for firms otherwise eligible, which over-states the
    number of firms at the reduced rate; the alternative — defaulting false — would
    understate it more. Recorded as an input so a better source can replace the
    assumption without touching a formula."""


class is_avant_report(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "IS de l'exercice précédent, pour l'assiette de la CEBGE"
    documentation = """The CEBGE is computed on an average of two exercices, so the
    prior year's IS is an input rather than something this system can derive: a
    single-year run has no memory of the year before."""


# --------------------------------------------------------------------------- #
# impôt sur les sociétés
# --------------------------------------------------------------------------- #
class eligible_taux_reduit(Variable):
    value_type = bool
    entity = Entreprise
    definition_period = YEAR
    label = "Éligibilité au taux réduit d'IS (CGI art. 219-I-b)"

    def formula(entreprise, period, parameters):
        p = parameters(period).impot_societes
        assez_petite = entreprise("chiffre_affaires", period) <= p.plafond_ca_taux_reduit
        capital = entreprise("capital_libere_detenu_personnes_physiques", period)
        return assez_petite * capital


class impot_societes(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "IS brut, avant contributions additionnelles"

    def formula(entreprise, period, parameters):
        p = parameters(period).impot_societes
        benefice = entreprise("benefice_imposable", period)
        eligible = entreprise("eligible_taux_reduit", period)
        # The reduced rate applies to a slice, not to the whole profit: a firm just
        # over the ceiling does not suddenly pay 25 % on its first euro.
        part_reduite = np.minimum(benefice, p.plafond_taux_reduit) * eligible
        return part_reduite * p.taux_reduit + (benefice - part_reduite) * p.taux_normal


class contribution_sociale_is(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Contribution sociale sur l'IS (CGI art. 235 ter ZC)"

    def formula(entreprise, period, parameters):
        p = parameters(period).impot_societes.contribution_sociale
        redevable = entreprise("chiffre_affaires", period) >= p.seuil_ca_exoneration
        assiette = np.maximum(entreprise("impot_societes", period) - p.abattement, 0.0)
        return assiette * p.taux * redevable


class impot_societes_total(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "IS et contributions additionnelles"

    def formula(entreprise, period, parameters):
        return (
            entreprise("impot_societes", period)
            + entreprise("contribution_sociale_is", period)
            + entreprise("cebge", period)
        )


# --------------------------------------------------------------------------- #
# C3S
# --------------------------------------------------------------------------- #
class c3s(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Contribution sociale de solidarité des sociétés (CSS art. L137-30 s.)"
    documentation = """An abattement, not a threshold: a firm one euro over 19 M€ of
    turnover pays 0.16 % of that one euro, not of 19 000 001 €. Getting this wrong
    puts a cliff into the effective-rate profile that does not exist."""

    def formula(entreprise, period, parameters):
        p = parameters(period).c3s
        assiette = np.maximum(entreprise("chiffre_affaires", period) - p.abattement, 0.0)
        return assiette * p.taux


# --------------------------------------------------------------------------- #
# placeholders — encoded once the primary sources are confirmed (M1)
# --------------------------------------------------------------------------- #
class cebge(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Contribution exceptionnelle sur les bénéfices des grandes entreprises"
    documentation = """Zero until the parameters are confirmed against the enacted
    finance laws. Present as a variable from the start so that everything
    downstream — the totals, the reform whitelist, the report — has its shape, and
    turning it on is a parameter change rather than a schema change."""
    default_value = 0.0


class cvae(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Cotisation sur la valeur ajoutée des entreprises"
    documentation = """Zero until the barème is confirmed. The progressive schedule
    below 50 M€ of turnover has to be taken from BOFiP verbatim; inventing its shape
    would be the firm-side equivalent of the barème-collapse defect that cost the
    household engine a 120 % marginal rate."""
    default_value = 0.0


class prelevements_entreprise(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Total des prélèvements modélisés sur l'entreprise"

    def formula(entreprise, period, parameters):
        return (
            entreprise("impot_societes_total", period)
            + entreprise("c3s", period)
            + entreprise("cvae", period)
        )


class taux_effectif(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Taux effectif d'imposition du bénéfice"
    documentation = """Total modelled tax over taxable profit. Zero for loss-makers
    rather than infinite: a firm with no profit has no effective rate on profit, and
    reporting one would put a meaningless spike in every distribution it enters."""

    def formula(entreprise, period, parameters):
        benefice = entreprise("benefice_imposable", period)
        total = entreprise("prelevements_entreprise", period)
        return np.where(benefice > 0, total / np.maximum(benefice, 1e-9), 0.0)


#: Every variable the system registers. Explicit rather than discovered by
#: introspection: a variable that silently fails to register computes its default
#: forever, which is exactly the class of silent wrongness this project keeps
#: finding.
VARIABLES = (
    chiffre_affaires,
    benefice_imposable,
    valeur_ajoutee,
    capital_libere_detenu_personnes_physiques,
    is_avant_report,
    eligible_taux_reduit,
    impot_societes,
    contribution_sociale_is,
    cebge,
    cvae,
    impot_societes_total,
    c3s,
    prelevements_entreprise,
    taux_effectif,
)
