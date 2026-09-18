"""Phase 8 M1 §3.1 — the debt identity, and the refusals that keep it honest.

    b_{t+1} = b_t × (1 + r_t) / (1 + g_t) − p_{t+1} + sfa_{t+1}

b is debt over GDP at Maastricht perimeter, r the implicit nominal rate on the stock, g
nominal GDP growth, p the primary balance over GDP with SURPLUS POSITIVE, sfa the
stock-flow adjustment over GDP.

**This is arithmetic, not economics.** The identity is exact given its inputs, and every
ounce of honesty in this module therefore lives in how the inputs are produced and labelled
rather than in the recurrence. A reader who takes a projected path for a forecast has been
misled by the labelling, not by the algebra — so the labelling is enforced by guards and
those guards have kill tests.

WHAT THIS MODULE REFUSES, AND WHY EACH REFUSAL IS A GUARD RATHER THAN A CONVENTION.

* **No path without a NAMED spending scenario.** Public spending is about 57 % of GDP and
  this project microsimulates only the transfer slice. A debt path rendered with taxes
  moving and spending silently held somewhere would imply that taxes alone carry the
  burden — an implication nobody typed and everybody would read. `project` raises when the
  scenario is absent; it never applies a default, because a default here is a political
  claim wearing an engineering default's clothes.
* **No probability language, anywhere.** These are scenarios crossed with bands, not
  distributions. There is no probability model behind any of it, so «confidence interval»,
  «likely» and «expected» are not available vocabulary — `SCENARIO_FORBIDDEN_WORDS` is an
  ALLOWLIST-shaped check on scenario names, because the denylist version of this idea is
  already on the record as a defect (`refuse_banded`).
* **A horizon cap.** Past it the arithmetic is exact and empty: the recurrence will happily
  return a number for 2085 and that number means nothing. Refused by name.

THE ONE INPUT THAT MAY NOT BE INVENTED. `sfa` defaults to zero for a PROJECTION, with a
banner saying so, because nobody can source a future stock-flow adjustment. For the
BACKTEST it is mandatory and must be realized: a backtest that drops a realized term and
still reproduces the path has been fitted, not tested. The asymmetry between the two entry
points is the whole point, and it is carried by the TYPE: `backtest` takes `RealizedYear`,
whose `sfa` has no default, so the term cannot be omitted rather than merely should not be.
`YearInputs.sfa` defaults to 0,0 and that is correct for a projection — which is exactly
why a backtest may not read it, since a default of zero is indistinguishable from a
realized zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Beyond this the recurrence still computes and the number stops meaning anything. Ten
#: years, recorded at M0 as the spec suggests; a caller asking for more is refused by name
#: rather than quietly truncated, because a silently shortened path looks like a finished one.
HORIZON_CAP_YEARS = 10

#: Vocabulary that would turn a scenario into a claim about likelihood. Checked on the
#: scenario NAME, which is what the chart displays. Written as the words that are refused
#: — but the check is `any(word in name)`, i.e. it can only ever reject: a name is accepted
#: by default and rejected on a listed word, so a new way of saying «probable» slips
#: through. That is a known limit of this shape and it is stated rather than hidden; the
#: allowlist version would require enumerating every acceptable scenario name in advance,
#: which the « trajectoire personnalisée » requirement forbids.
PROBABILITY_WORDS = ("probab", "likely", "confiance", "confidence", "chance",
                     "risque de", "attendu", "espéré", "prévision", "forecast")

#: How spending moves. One line of arithmetic each — this is NOT a spending microsimulation
#: and the banner says so on every chart.
SpendingRule = Literal["part_pib_constante", "gele_en_volume", "personnalise"]

BANNER = (
    "Les dépenses publiques (~57 % du PIB) ne sont PAS microsimulées ici ; seule la tranche "
    "des transferts l'est. Ce panneau est un scénario comptable."
)


class DebtError(RuntimeError):
    """A debt path was asked for in a way that would mislead."""


@dataclass(frozen=True)
class SpendingScenario:
    """A named spending path. The name is displayed on the chart, not in a tooltip.

    `rule` is one line of arithmetic, never a simulation. `growth` is used only by
    «personnalise» and is the nominal growth rate of the spending aggregate.
    """

    name: str
    rule: SpendingRule
    growth: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DebtError(
                "un scénario de dépense sans nom est un scénario invisible : le nom est ce "
                "qui s'affiche sur le graphique, et c'est la seule chose qui empêche un "
                "lecteur de prendre une hypothèse pour une donnée.")
        lowered = self.name.lower()
        hit = [w for w in PROBABILITY_WORDS if w in lowered]
        if hit:
            raise DebtError(
                f"le nom du scénario porte un vocabulaire de probabilité {hit} : rien ici "
                f"n'a de modèle de probabilité, et un scénario nommé « probable » est une "
                f"affirmation de vraisemblance que ce module ne peut pas soutenir.")
        if self.rule == "personnalise" and self.growth is None:
            raise DebtError(
                "« personnalisé » sans taux de croissance : la personnalisation EST le "
                "taux, et le défaut silencieux serait le scénario que personne n'a choisi.")
        if self.rule != "personnalise" and self.growth is not None:
            raise DebtError(
                f"un taux a été fourni avec la règle « {self.rule} », qui n'en lit aucun : "
                f"il serait ignoré en silence et le graphique afficherait un nom qui ne "
                f"décrit pas le calcul.")


#: The scenarios shipped at M1. Named, so the chart can display them, and frozen so a
#: caller cannot mutate one into something its name no longer describes.
SHIPPED: dict[str, SpendingScenario] = {
    "part_pib_constante": SpendingScenario(
        "Dépenses constantes en % du PIB", "part_pib_constante"),
    "gele_en_volume": SpendingScenario(
        "Dépenses gelées en volume", "gele_en_volume"),
}


@dataclass(frozen=True)
class YearInputs:
    """One year of the recurrence, each term named for what produced it."""

    year: int
    r: float
    """Implicit nominal rate on the stock. From §3.2 under a market SCENARIO, never a
    forecast."""
    g: float
    """Nominal GDP growth. A named scenario."""
    primary_balance: float
    """Primary balance over GDP, SURPLUS POSITIVE. Sign stated because the literature is
    split and a sign error here inverts the entire path while still looking plausible."""
    sfa: float = 0.0


@dataclass(frozen=True)
class DebtPoint:
    year: int
    ratio: float
    """Debt over GDP."""
    interest_ratio: float
    """b_t × r_t / (1+g_t) — the interest slice of the year's movement, for §3.6."""
    contribution_primary: float
    contribution_sfa: float


def step(ratio: float, inputs: YearInputs) -> DebtPoint:
    """One year of the identity, with its terms kept apart for the decomposition display.

    Separated from `project` so the arithmetic can be tested on a single year by hand.
    A recurrence that can only be checked end-to-end is a recurrence whose first year is
    never checked at all.
    """
    if inputs.g <= -1.0:
        raise DebtError(
            f"{inputs.year} : croissance nominale {inputs.g} ≤ −100 %, le dénominateur "
            f"(1+g) s'annule ou change de signe et le ratio n'a plus de sens.")
    snowball = ratio * (1.0 + inputs.r) / (1.0 + inputs.g)
    return DebtPoint(
        year=inputs.year,
        ratio=snowball - inputs.primary_balance + inputs.sfa,
        interest_ratio=ratio * inputs.r / (1.0 + inputs.g),
        contribution_primary=-inputs.primary_balance,
        contribution_sfa=inputs.sfa,
    )


def project(b0: float, years: list[YearInputs], *,
            spending: SpendingScenario | None = None) -> list[DebtPoint]:
    """The debt path. **Refuses without a named spending scenario.**

    The refusal is the point of the function, not a precondition on it: a path rendered
    with receipts moving and spending unstated would imply that taxes alone carry the
    burden, and that implication is exactly what this project exists not to make.
    """
    if spending is None:
        raise DebtError(
            "aucun scénario de dépense nommé : ce module REFUSE de rendre une trajectoire "
            "de dette sans lui. Les dépenses publiques pèsent ~57 % du PIB et seule la "
            "tranche des transferts est microsimulée ici ; une trajectoire où les recettes "
            "bougent et où la dépense reste tue laisserait entendre que l'impôt porte seul "
            "l'ajustement. Aucun défaut n'est appliqué : le choix est à l'appelant, et son "
            "nom s'affichera sur le graphique.")
    if not years:
        raise DebtError("aucune année : une trajectoire vide n'est pas une trajectoire")
    if len(years) > HORIZON_CAP_YEARS:
        raise DebtError(
            f"{len(years)} années demandées, plafond {HORIZON_CAP_YEARS} : au-delà de "
            f"l'horizon, l'arithmétique est exacte et vide.")

    out: list[DebtPoint] = []
    ratio = b0
    for entry in years:
        point = step(ratio, entry)
        out.append(point)
        ratio = point.ratio
    return out

# ---------------------------------------------------------------- §6.1 backtest

@dataclass(frozen=True)
class RealizedYear:
    """One REALIZED year. Every term is an observation, and `sfa` has NO default.

    This type exists precisely because `YearInputs.sfa` defaults to 0,0. A backtest
    reading that field could not distinguish « l'ajustement flux-stocks réalisé vaut
    zéro » from « l'appelant ne l'a jamais renseigné » — and those two are the
    difference between a test and a fit. Dropping the default moves the refusal from a
    runtime check that can be forgotten to a constructor that cannot be called without
    the term.
    """

    year: int
    r: float
    """Implicit nominal rate REALIZED: charge d'intérêts D.41 rapportée au stock."""
    g: float
    """Nominal GDP growth REALIZED."""
    primary_balance: float
    """Solde primaire réalisé sur PIB, EXCÉDENT POSITIF — même convention que
    `YearInputs`, restatée parce qu'une inversion de signe ici retourne toute la
    trajectoire en gardant une allure plausible."""
    sfa: float
    """Ajustement flux-stocks RÉALISÉ. Sans défaut, exprès."""
    published_ratio: float
    """Le b_t publié, pour la comparaison année par année."""


@dataclass(frozen=True)
class BacktestPoint:
    year: int
    modelled_ratio: float
    published_ratio: float
    residual: float
    """modelled − published, en points de PIB. Signé : le sens porte l'information."""
    within: bool


def backtest(b0: float, years: list[RealizedYear], *, tolerance: float) -> list[BacktestPoint]:
    """L'identité §3.1 sur des entrées RÉALISÉES, comparée au b publié.

    **Aucun scénario de dépense n'est demandé, et c'est délibéré.** `project` en exige
    un parce que la dépense FUTURE est un choix que personne n'a fait ; la dépense
    PASSÉE est un fait déjà contenu dans le solde primaire réalisé. Réclamer un scénario
    ici laisserait croire qu'on en a choisi un, alors qu'on n'a rien choisi du tout.

    **L'asymétrie sur le SFA est ce que cette fonction fait respecter.** Elle est portée
    par le type : `RealizedYear.sfa` n'a pas de défaut. S'y ajoute un refus que le type
    ne peut pas porter — une série identiquement nulle sur toutes les années, qui est la
    signature du défaut de `YearInputs` recopié sous une étiquette « réalisé ».
    """
    if not years:
        raise DebtError("aucune année réalisée : un backtest sans année ne teste rien")
    if len(years) > HORIZON_CAP_YEARS:
        raise DebtError(
            f"{len(years)} années réalisées, plafond {HORIZON_CAP_YEARS}")

    ordered = sorted(years, key=lambda y: y.year)
    expected = list(range(ordered[0].year, ordered[0].year + len(ordered)))
    if [y.year for y in ordered] != expected:
        raise DebtError(
            f"les années réalisées ne sont pas consécutives ({[y.year for y in ordered]}) : "
            f"la récurrence enchaîne b_t sur b_{{t+1}}, donc un trou ferait passer le "
            f"report d'une année pour celui d'une autre, sans erreur visible.")
    if any(y.sfa is None for y in ordered):
        raise DebtError(
            "un ajustement flux-stocks vaut None : il est OBLIGATOIRE pour un backtest. "
            "Un backtest qui laisse tomber un terme réalisé et reproduit quand même la "
            "trajectoire a été ajusté, pas testé.")
    if all(y.sfa == 0.0 for y in ordered):
        raise DebtError(
            f"l'ajustement flux-stocks est identiquement nul sur les {len(ordered)} "
            f"années : historiquement il ne l'est pas, et cette série est la signature "
            f"du défaut de `YearInputs.sfa` recopié sous une étiquette « réalisé ». "
            f"REFUSÉ plutôt qu'accepté avec bannière, parce qu'ici le terme n'est pas "
            f"une simplification assumée mais la moitié de ce que le test mesure.")
    if tolerance <= 0:
        raise DebtError(
            "une tolérance nulle ou négative : un backtest dont rien ne peut sortir de "
            "la bande ne mesure rien.")

    out: list[BacktestPoint] = []
    ratio = b0
    for entry in ordered:
        point = step(ratio, YearInputs(
            year=entry.year, r=entry.r, g=entry.g,
            primary_balance=entry.primary_balance, sfa=entry.sfa))
        residual = point.ratio - entry.published_ratio
        out.append(BacktestPoint(
            year=entry.year, modelled_ratio=point.ratio,
            published_ratio=entry.published_ratio, residual=residual,
            within=abs(residual) <= tolerance))
        # Le report enchaîne sur le MODÈLE, pas sur le publié. Repartir du publié
        # chaque année re-calerait la trajectoire à chaque pas et ne testerait plus que
        # sept transitions d'un an isolées — ce qui passerait toujours.
        ratio = point.ratio
    return out
