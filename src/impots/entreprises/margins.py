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

#: C3S receipts by the year they were BOOKED. A tax assessed on prior-year turnover
#: has to be graded against the year after the turnover it was computed on: a
#: population whose turnover is 2023 produces the C3S booked in 2024. Declaring the
#: mismatch as a bias was the weaker answer; selecting the comparable vintage is the
#: correct comparison, and `reconcile` does the selection from the population's own
#: vintage rather than from whichever figure is nearest.
C3S_BY_BOOKING_YEAR: dict[int, Figure] = {}

C3S = Figure(
    value=5.337e9, unit="EUR", year=2025,
    scope="C3S encaissée, tous redevables",
    source="Rapport à la Commission des comptes de la Sécurité sociale, mai 2026",
    url=CCSS_2026, use="validation",
    caveat="Cross-checked to the euro-million against INSEE tableau 3.217. Assessed on "
           "2024 turnover: C3S due in year N is levied on year N-1 turnover.",
)

C3S_2024 = Figure(
    value=5.228e9, unit="EUR", year=2024,
    scope="C3S encaissée en 2024, assise sur le chiffre d'affaires 2023",
    source="Rapport à la Commission des comptes de la Sécurité sociale, mai 2026 ; "
           "INSEE tableau 3.217", url=CCSS_2026, use="validation",
    caveat="The comparable vintage for a population whose turnover is 2023.",
)

C3S_BY_BOOKING_YEAR.update({2024: C3S_2024, 2025: C3S})


def c3s_for_turnover_year(vintage: int | None) -> tuple[Figure, str]:
    """The C3S receipt assessed on `vintage` turnover, i.e. the one booked a year later.

    Returns the figure and a sentence saying why it is the right one. Falls back to
    the most recent receipt when the vintage is unknown or unpublished, and says so —
    a fallback that quietly picked the nearest figure would be the whole problem.
    """
    if vintage is not None and (vintage + 1) in C3S_BY_BOOKING_YEAR:
        figure = C3S_BY_BOOKING_YEAR[vintage + 1]
        return figure, (
            f"Graded against the C3S booked in {vintage + 1}, which is the receipt "
            f"assessed on {vintage} turnover — the vintage this population carries. "
            f"C3S due in year N is levied on year N-1 turnover, so comparing against "
            f"the same year's receipt would be off by a year of nominal growth."
        )
    latest = max(C3S_BY_BOOKING_YEAR)
    return C3S_BY_BOOKING_YEAR[latest], (
        f"No published receipt is assessed on this population's turnover vintage "
        f"({vintage}), so the {latest} booking is shown instead. That receipt is "
        f"assessed on {latest - 1} turnover and the comparison is off by the "
        f"difference in years — read it as an order of magnitude, not a residual."
    )

IS_NET_DGFIP = Figure(
    value=61.8e9, unit="EUR", year=2025,
    scope="IS net et contribution sociale sur les bénéfices, encaissements DGFiP tous "
          "affectataires",
    source="DGFiP Statistiques n° 43, mars 2026, tableau 1", url=DGFIP_STAT_39,
    use="context",
    caveat="A third published 2025 headline, 1.9 bn above the budget line because it "
           "bundles the contribution sociale. Recorded so that a reader grading this "
           "model against 'the DGFiP figure' knows which of the three they have.",
)

CVAE = Figure(
    value=4.024e9, unit="EUR", year=2025,
    scope="CVAE, ligne 1497 du budget de l'État",
    source="Exécution budgétaire 2025 ; Voies et moyens tome I, PLF 2026",
    url=BUDGET_2025, use="validation",
    caveat="Three perimeters, all 2025: budget line 1497 at 4.024 bn (State share only), "
           "DGFiP collections all-affectataires at 4.5 bn (the ~0.5 bn difference is the "
           "taxe additionnelle pour frais de CCI, which the model does not levy), and "
           "national accounts at 3.749 bn on an accrual basis. All at a 0.19 % maximum "
           "rate against a simulated year at 0.28 %.",
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
    scope="Série publiée « Taux moyen d'imposition », graphique 2 de DGFiP Stat n° 39 "
          "(valeur 2024 : 24,256 %) — IS brut rapporté aux bénéfices déclarés",
    source="DGFiP Statistiques n° 39, septembre 2025, graphique 2",
    url=DGFIP_STAT_39, use="validation",
    caveat="The construction is named on purpose. Tableau 2 of the same publication gives "
           "24.32 % for what looks like the same ratio, and graphique 2's own denominator "
           "gives 24.34 % — three constructions within one publication, differing by 0.08 "
           "point. This line is the one the 'who pays' reconciliation is graded on, so it "
           "is pinned to the published series and held there. Separately: loss-makers "
           "leave BOTH sides here, which is why this series orders the sizes the opposite "
           "way from the INSEE implicit rate. The model's own statistic is a third object "
           "again — denominator is taxable profit, like this one, but loss-makers stay in "
           "the average at zero, like the other.",
)


TAXABLE_PROFIT = Figure(
    value=283.950641563e9, unit="EUR", year=2024,
    scope="Bénéfices déclarés par les entreprises bénéficiaires à l'IS, toutes tailles",
    source="DGFiP Statistiques n° 39, septembre 2025, tableau 2",
    url=DGFIP_STAT_39, use="calibration",
    caveat="**Spent.** The cell table's fiscal-to-accounting ratio is computed to "
           "reproduce this total exactly, so hitting it is the build working. Its "
           "consequence travels: the IS *level* is calibrated through it, and only the "
           "IS *rate* on the synthetic distribution stays free.",
)

IS_BRUT_BY_SIZE: dict[str, float] = {
    "micro": 14.03225e9, "PME": 19.224701e9, "ETI": 16.208329e9, "GE": 19.58231e9,
}
"""IS brut by size class, DGFiP Statistiques n° 39 tableau 2 (2024). The profile the
firm module exists to reproduce, and untouched by any calibration here."""


#: IS brut by DGFiP sector grouping, with the NAF sections each covers.
#:
#: THE MODULE'S BEST VALIDATION DIMENSION, and the only one of the two obvious ones
#: that is like-for-like. Size cannot be graded against DGFiP: its TPE/PME/ETI/GE
#: buckets are fiscal, INSEE's MIC/PME/ETI/GE are the LME decree applied to profiled
#: enterprises, and the two do not coincide — DGFiP counts 220 600 PME where INSEE
#: counts 164 000, so a by-size residual measures the taxonomy gap rather than the
#: model. Sectors are NAF in both sources, so a by-sector residual measures the model.
#:
#: Nothing in the cell table is calibrated by sector: the sector shape comes from
#: Ésane and the calibration is national and by size class, so these lines are free.
IS_BRUT_BY_SECTOR: dict[str, tuple[float, tuple[str, ...]]] = {
    "Industrie": (15.229616141e9, ("B", "C", "D", "E")),
    "Commerce, transports, hébergement": (18.914007452e9, ("G", "H", "I")),
    "Construction": (4.981431577e9, ("F",)),
    "Activités spécialisées et de soutien": (9.167166289e9, ("M", "N")),
    "Activités immobilières": (3.859014398e9, ("L",)),
    "Information et communication": (3.529089404e9, ("J",)),
}

IS_BY_SECTOR_SOURCE = "DGFiP Statistiques n° 39, septembre 2025, tableau 1 (millésime 2024)"


def is_sector_figure(label: str, value: float) -> Figure:
    """A published sector IS total, as a Figure so it carries its own `use`."""
    return Figure(
        value=value, unit="EUR", year=2024,
        scope=f"IS brut des entreprises imposées à l'IS — {label}",
        source=IS_BY_SECTOR_SOURCE, url=DGFIP_STAT_39, use="validation",
        caveat="Free: the cell table's sector shape comes from Ésane and its "
               "calibration is national and by size, so nothing here was fitted to "
               "this figure.",
    )


def figures_by_use(use: Use) -> dict[str, Figure]:
    """Every module-level `Figure` declared with the given use."""
    return _figures_by_use(globals(), use)
