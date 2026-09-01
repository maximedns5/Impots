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
    single-year run has no memory of the year before.

    The formula below is the **stationarity assumption, made explicit**: absent a
    prior year, the firm is assumed to have earned the same IS as this year. A
    population that carries a real prior-year IS overrides it, because an input
    always beats a formula in OpenFisca. Defaulting to zero instead would halve
    every CEBGE base silently, which is the class of quiet wrongness this project
    keeps finding (D-005, D-011)."""

    def formula(entreprise, period, parameters):
        return entreprise("impot_societes", period)


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
# CEBGE et CVAE
# --------------------------------------------------------------------------- #
def _arrondi_au_pas(taux, pas):
    """Round a rate half-up to a step, the way both statutes require.

    Not `np.round`, which is round-half-to-even. The CVAE statute says the rate is
    "exprimé en pourcentages et arrondi au centième le plus proche" and the CEBGE
    statute spells out half-up ("le second décimal majoré d'une unité si le suivant
    est supérieur ou égal à 5"). Skipping this turns a step function into a
    continuous one and biases the CVAE rate by up to ±6 % at the bottom of the
    schedule."""
    return np.floor(taux / pas + 0.5) * pas


class cebge(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Contribution exceptionnelle sur les bénéfices des grandes entreprises"
    documentation = """LF 2025 art. 48, prorogé et modifié par LF 2026 art. 12. Not
    codified: it lives in a finance law, not in the CGI.

    Two features that a naive reading misses, and that dominate the yield. The base
    is the **average of two exercices' IS**, not this year's — so a firm whose
    profit collapsed still pays on the average. And the rate is **smoothed** over a
    100 M€ band above each threshold, rising linearly from zero: without it a firm
    at 1.50 bn would pay what a firm at 1.49 bn does not.

    **The two-exercice tests are collapsed onto one year here.** The statute tests
    turnover on the current *and* prior exercice (rate) or *either* (liability); our
    population has a single year, so `is_avant_report` supplies the stationarity
    assumption and turnover is read once. For a synthetic population whose firms are
    independent draws this adds no fiction that is not already present, but it does
    mean the model cannot show the entry and exit effects the second exercice's
    rules create — which is exactly where the 2026 yield moves."""

    def formula(entreprise, period, parameters):
        p = parameters(period).cebge
        ca = entreprise("chiffre_affaires", period)
        # A parameter whose values are all null is *removed* from the tree, not set
        # to None — so this is `hasattr`, not an `is None` check. Getting that wrong
        # raises ParameterNotFoundError deep in a formula instead of returning zero.
        if not hasattr(p, "taux_base"):  # after the second exercice, the tax is gone
            return np.zeros_like(ca)

        # Base: the mean of this exercice's IS and the previous one's, before any
        # crédit d'impôt. Our IS is already before crédits — the model has none.
        assiette = 0.5 * (
            entreprise("impot_societes", period) + entreprise("is_avant_report", period)
        )

        largeur = p.lissage.largeur
        t1, t2 = p.taux_base, p.taux_majore
        taux = np.select(
            [
                ca < p.seuil_ca,
                ca < p.lissage.borne_haute,
                ca < p.seuil_ca_taux_majore,
                ca < p.lissage.borne_haute_taux_majore,
            ],
            [
                0.0,
                t1 * (ca - p.seuil_ca) / largeur,
                t1,
                t1 + (t2 - t1) * (ca - p.seuil_ca_taux_majore) / largeur,
            ],
            default=t2,
        )
        return assiette * _arrondi_au_pas(taux, 0.0001)


class cvae(Variable):
    value_type = float
    entity = Entreprise
    definition_period = YEAR
    label = "Cotisation sur la valeur ajoutée des entreprises"
    documentation = """CGI art. 1586 ter à 1586 septies, barème de l'art. 1586
    quater I.

    The schedule is **continuous, not marginal**: each formula gives the average
    rate applied to the whole value added, so there are no stacked brackets here and
    the household module's barème machinery does not apply. Three official worked
    examples pin it (CA 2.7 M€ → 0.08 %, 6.2 M€ → 0.17 %, 40.1 M€ → 0.28 %) and are
    kept as tests.

    **The base is a proxy and it is biased downward.** CVAE value added is not
    accounting value added: rents, crédit-bail and location-gérance are intermediate
    consumption in accounting but are *not* deductible from the CVAE base. Our
    population carries the accounting figure from ESANE, so the assiette is
    understated, most for firms that lease their assets — which is correlated with
    sector, so it distorts the incidence table and not only the total."""

    def formula(entreprise, period, parameters):
        p = parameters(period).cvae
        ca = entreprise("chiffre_affaires", period)
        if not hasattr(p, "taux_max"):  # abrogée au 1er janvier 2030
            return np.zeros_like(ca)

        bornes, bareme = p.bornes, p.bareme
        taux = np.select(
            [ca <= bornes.seuil_taux_nul, ca <= bornes.t1_t2, ca <= bornes.t2_t3,
             ca <= bornes.t3_t4],
            [
                0.0,
                bareme.pente_t1 * (ca - bornes.seuil_taux_nul)
                / (bornes.t1_t2 - bornes.seuil_taux_nul),
                bareme.base_t2 + bareme.pente_t2 * (ca - bornes.t1_t2)
                / (bornes.t2_t3 - bornes.t1_t2),
                bareme.base_t3 + bareme.pente_t3 * (ca - bornes.t2_t3)
                / (bornes.t3_t4 - bornes.t2_t3),
            ],
            default=p.taux_max,
        )
        # The rounding is prescribed for the b, c and d brackets only — not for the
        # e ceiling, which is already an exact rate.
        taux = np.where(
            ca > bornes.t3_t4, taux, _arrondi_au_pas(taux, bareme.arrondi)
        )

        # Value added is capped as a share of turnover, which bites on labour-heavy
        # firms and, when it bites, dominates their assiette.
        plafond = np.where(
            ca <= p.plafond_va.seuil_ca, p.plafond_va.taux_bas, p.plafond_va.taux_haut
        )
        assiette = np.minimum(entreprise("valeur_ajoutee", period), plafond * ca)

        degrevement = (ca <= p.degrevement.seuil_ca) * p.degrevement.montant
        due = np.maximum(assiette * taux - degrevement, 0.0)
        # Two different thresholds, and conflating them is the classic error: 152 500 €
        # is the scope test, while below 500 000 € the rate is simply nil. On top of
        # both sits a franchise — since 2024 there is no minimum contribution, so the
        # CVAE is owed from 64 €, not from 63 €.
        return np.where((ca > p.seuil_assujettissement) & (due > p.franchise), due, 0.0)


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
