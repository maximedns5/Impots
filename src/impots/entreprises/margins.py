"""Published figures the firm module is calibrated to and validated against (§3.4).

Same rule as the household side, and it is the only reason this report is worth
reading: **a figure used to calibrate is spent and can never afterwards be a
validation line.** Each entry declares which it is, next to its source, and the
`use` travels with the figure into the report — so a line cannot be tagged one way
here and another way in the table.

## What is spent, for this population

The cell table fixes each sector × size cell's **firm count**, **turnover** and
**value added** exactly, and its **P(loss)**. All four are therefore calibration:
reproducing them proves the build works, nothing more.

**Profit is not calibrated**, which is what leaves the IS line able to say
something — with one caveat that has to be stated rather than buried. The
fiscal-to-accounting ratio is derived from published DGFiP assiette totals, and
assiette x rate is approximately receipts, so the IS line is *semi*-independent in
exactly the way the household module's income-tax line is semi-independent of a
calibrated wage bill.

## The comparator trap on effective rates

There are two published effective-rate-by-size series and **they order the sizes in
opposite directions**. They are not in conflict; they measure different things.

* *Insee Analyses 112* divides IS brut by **excédent net d'exploitation**, over all
  firms with positive ENE. Loss-makers stay in the denominator and drag the rate
  down, so the rate falls with size: 14.3 % for grandes entreprises against 21.4 %
  for PME.
* *DGFiP Statistiques 39* divides IS brut by the **declared profits of profitable
  firms**. Loss-makers leave both sides, and the ordering reverses.

Picking whichever one the model happens to resemble would be the purest form of
calibrating to a validation line. Both are recorded, the model's own statistic is
described exactly, and the report states which object it is closest to.
"""

from __future__ import annotations

from impots.reporting import Figure, Use
from impots.reporting import figures_by_use as _figures_by_use

BUDGET_2025 = "https://www.budget.gouv.fr/documentation/file-download/33360"
INSEE_COMPTES = "https://www.insee.fr/fr/statistiques/fichier/8571311/t_3217.xlsx"
DGFIP_STAT_39 = "https://www.impots.gouv.fr/statistiques"
INSEE_ANALYSES_112 = "https://www.insee.fr/fr/statistiques/8582116"
CCSS_2026 = "https://www.securite-sociale.fr/accueil/rapport-ccss-mai-2026"

# --------------------------------------------------------------------------- #
# Impôt sur les sociétés
#
# Three published IS numbers, and choosing between them is most of the work. Our
# model computes IS *before* any crédit d'impôt (it has none) and before the
# remboursements et dégrèvements that turn gross into net. The national-accounts
# "avant crédits d'impôt" line is therefore the right comparator, and the budget's
# net receipts are shown only to make the gap visible.
# --------------------------------------------------------------------------- #
IS_AVANT_CREDITS = Figure(
    value=69.473e9, unit="EUR", year=2025,
    scope="IS avant crédits d'impôt, comptabilité nationale, ensemble des sociétés",
    source="INSEE, comptes nationaux base 2020, tableau 3.217",
    url=INSEE_COMPTES, use="validation",
    caveat="The comparator this model should be judged against: it has no CIR and no "
           "other créance, so a net figure would be missed high by construction.",
)

IS_NET_RECETTES = Figure(
    value=59.918e9, unit="EUR", year=2025,
    scope="IS net des remboursements et dégrèvements, recettes budgétaires de l'État",
    source="Exécution budgétaire 2025 (DGFiP/Direction du budget) ; Cour des comptes, "
           "Le budget de l'État en 2025",
    url=BUDGET_2025, use="context",
    caveat="Net of 24.6 bn of remboursements et dégrèvements and excluding the "
           "contribution sociale, the CEBGE and Pilier 2, which are separate budget "
           "lines. Shown to size the gap, not to be hit.",
)

IS_BRUT = Figure(
    value=84.523e9, unit="EUR", year=2025,
    scope="IS brut, ligne 1301 du budget de l'État, avant remboursements",
    source="Exécution budgétaire 2025, tableaux 2 et 3", url=BUDGET_2025, use="context",
    caveat="Gross of restitutions, so it double-counts instalments later refunded.",
)

CONTRIBUTION_SOCIALE = Figure(
    value=1.459e9, unit="EUR", year=2025,
    scope="Contribution sociale sur l'IS (3,3 %), ligne 1302 du budget de l'État",
    source="Exécution budgétaire 2025, tableau 3", url=BUDGET_2025, use="validation",
    caveat="National accounts put the same object at 1.151 bn on an accrual basis; the "
           "0.3 bn spread between them is larger than most tolerances here.",
)

CEBGE = Figure(
    value=7.520e9, unit="EUR", year=2025,
    scope="Contribution exceptionnelle sur les bénéfices des grandes entreprises, "
          "premier exercice (ligne 1441)",
    source="Exécution budgétaire 2025 ; INSEE tableau 3.217 ; Cour des comptes",
    url=BUDGET_2025, use="validation",
    caveat="2025 is the CEBGE's FIRST exercice, at a 1 bn threshold. The model runs 2026, "
           "the second, at 1.5 bn tested on that year alone — a different population of "
           "payers, so this line sizes the instrument rather than scoring the year.",
)

C3S = Figure(
    value=5.337e9, unit="EUR", year=2025,
    scope="C3S encaissée, tous redevables",
    source="Rapport à la Commission des comptes de la Sécurité sociale, mai 2026",
    url=CCSS_2026, use="validation",
    caveat="Cross-checked to the euro-million against INSEE tableau 3.217.",
)

CVAE = Figure(
    value=4.024e9, unit="EUR", year=2025,
    scope="CVAE, ligne 1497 du budget de l'État",
    source="Exécution budgétaire 2025 ; Voies et moyens tome I, PLF 2026",
    url=BUDGET_2025, use="validation",
    caveat="National accounts put 2025 at 3.749 bn on an accrual basis. Both are 2025, at "
           "a 0.19 % maximum rate; the model runs 2026 at 0.28 %, so the published figure "
           "is not a target for the simulated year and is scaled in the note.",
)

# --------------------------------------------------------------------------- #
# Population structure — all CALIBRATION. The cell table sets these directly.
# --------------------------------------------------------------------------- #
FIRMS_LIABLE = Figure(
    value=2_718_377, unit="count", year=2024,
    scope="Entreprises redevables de l'IS (unités légales)",
    source="DGFiP Statistiques n° 39, septembre 2025", url=DGFIP_STAT_39,
    use="calibration",
    caveat="Spent: the cell table fixes the firm count per cell, so this is reproduced by "
           "construction rather than found.",
)

SHARE_NO_TAXABLE_PROFIT = Figure(
    value=0.375, unit="ratio", year=2024,
    scope="Part des redevables de l'IS sans bénéfice imposable positif",
    source="DGFiP Statistiques n° 39, septembre 2025 (972 000 déficitaires sur 2 718 377, "
           "plus environ 1,7 % à résultat nul)", url=DGFIP_STAT_39,
    use="calibration",
    caveat="Spent: P(loss) is an input to each cell's Bernoulli draw. It is listed because "
           "getting it wrong makes every other IS line meaningless, not because hitting it "
           "is evidence.",
)

#: Share of firms with no positive taxable profit, by size — the only published size
#: breakdown of it, and the shape the per-cell Bernoulli should follow.
SHARE_NO_PROFIT_BY_SIZE: dict[str, float] = {
    "micro": 0.398, "PME": 0.211, "ETI": 0.217, "GE": 0.245,
}

# --------------------------------------------------------------------------- #
# Effective rates — the shape lines, and the two of them disagree by construction
# --------------------------------------------------------------------------- #
IMPLICIT_RATE_GE = Figure(
    value=0.143, unit="ratio", year=2022,
    scope="Taux implicite d'IS brut des grandes entreprises : IS brut / excédent net "
          "d'exploitation, pondéré par l'ENE, contribution sociale incluse, avant crédits",
    source="INSEE Analyses n° 112, septembre 2025 (Arnal, Di Nallo, Martin), figure 4",
    url=INSEE_ANALYSES_112, use="context",
    caveat="Denominator is ENE over all firms with positive ENE, so loss-makers pull the "
           "rate DOWN and it falls with size. Not the model's statistic.",
)

IMPLICIT_RATE_PME = Figure(
    value=0.214, unit="ratio", year=2022,
    scope="Taux implicite d'IS brut des PME, même définition",
    source="INSEE Analyses n° 112, septembre 2025, figure 4",
    url=INSEE_ANALYSES_112, use="context",
    caveat="Paired with the GE figure: published series ordering that the model's own "
           "effective rate is not expected to reproduce, because it measures another thing.",
)

AVERAGE_RATE_ON_PROFITS = Figure(
    value=0.2426, unit="ratio", year=2024,
    scope="IS brut rapporté aux bénéfices déclarés des entreprises bénéficiaires",
    source="DGFiP Statistiques n° 39, septembre 2025, graphique 2",
    url=DGFIP_STAT_39, use="validation",
    caveat="Loss-makers leave BOTH sides here, which is why this series orders the sizes "
           "the opposite way from the INSEE implicit rate. The model's own effective rate "
           "sits between the two objects: its denominator is taxable profit, like this one, "
           "but loss-makers stay in the average at zero, like the other.",
)


def figures_by_use(use: Use) -> dict[str, Figure]:
    """Every module-level `Figure` declared with the given use."""
    return _figures_by_use(globals(), use)
