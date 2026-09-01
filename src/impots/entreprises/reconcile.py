"""The firm module's reconciliation report (§5) — its credibility page.

Same engine as the household report (`impots.reporting`), same discipline: every
line states its residual against a published total and says whether that total was
spent on calibration. This module only decides *which lines a firm population has*.

One thing is specific to this module and is printed before anything else. The
population's skeleton comes from a **cell table**, and when that table is the
committed fixture rather than SIRENE x ESANE, every published total below is being
compared against invented cells. The residuals are then arithmetic about a fiction
and validate nothing at all. The report says so at the top, in those words, rather
than letting a reader meet a tidy table and draw the obvious wrong conclusion.
"""

from __future__ import annotations

from pathlib import Path

from impots import reporting
from impots.entreprises import margins
from impots.entreprises.aggregate import FirmAggregates

REPORTS = Path(__file__).resolve().parents[3] / "reports"

#: Declared tolerances (D-024). Declared, not silently passed: a line outside its
#: tolerance prints as such and the report says the module is not ready.
#:
#: `is` is the ship gate at +/-20 %. It is wide because one modelling choice — the
#: single national fiscal-to-accounting ratio — dominates it, and narrowing the gate
#: would only invite tuning that ratio until the line goes green, which is precisely
#: the move this project refuses. `instrument` is wider still: the C3S and CVAE bases
#: are proxied from accounting aggregates, and the CEBGE's published year is not the
#: simulated one.
TOLERANCE = {"calibration": 0.01, "is": 0.20, "instrument": 0.25, "shape": 0.15}

Line = reporting.Line

INTRO = (
    "How far the synthetic firm population's simulated aggregates sit from published "
    "national totals. Read the fidelity column before the residual column: several "
    "lines here are reproduced by construction and prove only that the build works."
)

SYNTHETIC_WARNING = (
    "> **These residuals mean nothing.** This population was built from the committed "
    "fixture cell table, which is invented — not from SIRENE and ESANE. Every published "
    "figure below is therefore being compared against made-up sector totals, and a line "
    "that lands inside its tolerance has done so by coincidence. The table is here to "
    "show that the machinery runs end to end; it is not evidence about French corporate "
    "tax. Build from a real cell table before quoting a single number from this page."
)


def build_lines(agg: FirmAggregates, year: int) -> list[Line]:
    """Every reconciliation line this population has, calibration and validation alike."""
    totals = agg.totals
    lines: list[Line] = [
        Line.from_figure(
            margins.IS_AVANT_CREDITS, "Impôt sur les sociétés",
            totals.get("impot_societes"), TOLERANCE["is"],
            "**The ship gate.** Semi-independent: profit is not calibrated, but the "
            "fiscal-to-accounting ratio that converts it is derived from published DGFiP "
            "assiette totals, so this line is not fully free of its sources. Biased "
            "upward by the absence of loss carry-forward, and upward again by treating "
            "every group member as a separate unit.",
            source="INSEE comptes nationaux",
        ),
        Line.from_figure(
            margins.IS_NET_RECETTES, "IS — recettes nettes (pour mémoire)",
            totals.get("impot_societes"), TOLERANCE["is"],
            "Expected to be missed high, and shown for that reason: this figure is net of "
            "24.6 bn of remboursements et dégrèvements and of every crédit d'impôt, none "
            "of which the model has.",
            source="budget.gouv.fr",
        ),
        Line.from_figure(
            margins.CONTRIBUTION_SOCIALE, "Contribution sociale sur l'IS",
            totals.get("contribution_sociale_is"), TOLERANCE["instrument"],
            "Mechanically downstream of the IS line — it is 3.3 % of IS above a 763 000 € "
            "abattement — so it carries the IS residual plus the composition of firms "
            "around that abattement, and is not independent evidence.",
            source="budget.gouv.fr",
        ),
        Line.from_figure(
            margins.CEBGE, "Contribution exceptionnelle (CEBGE)",
            totals.get("cebge"), TOLERANCE["instrument"],
            f"Published for 2025, the CEBGE's *first* exercice at a 1 bn threshold; the "
            f"model runs {year}, the second, at 1.5 bn tested on that year alone. Different "
            "payers, so this sizes the instrument rather than scoring the year — and the "
            "model's stationarity assumption (D-022) cannot represent the entries and "
            "exits that threshold creates.",
            source="budget.gouv.fr",
        ),
        Line.from_figure(
            margins.CVAE, "CVAE", totals.get("cvae"), TOLERANCE["instrument"],
            "Published for 2025 at a 0.19 % maximum rate against a simulated year at "
            "0.28 %, so a like-for-like comparison would scale the published figure by "
            "roughly 1.47 before reading the residual. Biased downward by the accounting "
            "value-added proxy, which does not add back rents and crédit-bail (D-021).",
            source="budget.gouv.fr",
        ),
        Line.from_figure(
            margins.C3S, "C3S", totals.get("c3s"), TOLERANCE["instrument"],
            "The cleanest line in the table: the base is turnover, which is calibrated per "
            "cell, and the rate is a flat 0.16 % above a 19 M€ abattement. A residual here "
            "is almost entirely the distribution of turnover *within* cells — the one "
            "thing in the population that no published source constrains.",
            source="CCSS",
        ),
        Line.from_figure(
            margins.FIRMS_LIABLE, "Entreprises redevables", agg.n_firms,
            TOLERANCE["calibration"],
            "**Spent.** The cell table fixes the firm count per cell and the build "
            "reproduces it exactly; a non-zero residual here would mean the weighting "
            "broke, which is what the guard around it exists to catch.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.SHARE_NO_TAXABLE_PROFIT, "Part sans bénéfice imposable",
            agg.share_zero_is, TOLERANCE["calibration"],
            "**Spent.** P(loss) is an input to each cell's Bernoulli draw. It is printed "
            "because every IS line above is meaningless if it is wrong — not because "
            "hitting it is evidence.",
            source="DGFiP",
        ),
    ]

    if agg.by_size:
        by_size = {row.taille: row for row in agg.by_size}
        weighted = sum(row.mean_effective_rate * row.n_firms for row in agg.by_size)
        firms = sum(row.n_firms for row in agg.by_size)
        lines.append(Line.from_figure(
            margins.AVERAGE_RATE_ON_PROFITS, "Taux effectif moyen",
            weighted / firms if firms else None, TOLERANCE["shape"],
            "Read the caveat before the residual. The model's statistic is not either "
            "published one: its denominator is taxable profit (like DGFiP's) but "
            "loss-makers stay in the average at zero (like INSEE's). It should therefore "
            "land *below* the DGFiP figure by roughly the share of loss-makers, and a "
            "line that matched it exactly would be the suspicious outcome.",
            source="DGFiP",
        ))
        if "GE" in by_size and "PME" in by_size:
            lines.append(Line(
                label="Écart de taux effectif GE − PME",
                simulated=by_size["GE"].mean_effective_rate - by_size["PME"].mean_effective_rate,
                published=margins.IMPLICIT_RATE_GE.value - margins.IMPLICIT_RATE_PME.value,
                unit="ratio", source="INSEE Analyses 112", use="context",
                tolerance=TOLERANCE["shape"],
                note="Context only, and it is expected to have the WRONG SIGN. INSEE's "
                     "implicit rate falls with size because its denominator is ENE over all "
                     "firms including loss-makers; the model's rises with size because C3S "
                     "and CVAE hit turnover and value added whether or not there is a "
                     "profit. The two measure different objects, and picking whichever one "
                     "the model resembles would be calibrating to a validation line.",
                figure_use="context",
            ))
    return lines


def method_notes(agg: FirmAggregates, fiscal_to_accounting: float | None) -> list[str]:
    """The choices that dominate the residuals, stated as prose rather than as a column."""
    ratio = (
        f"**Fiscal-to-accounting ratio: {fiscal_to_accounting:.3f}.** "
        if fiscal_to_accounting is not None
        else "**Fiscal-to-accounting ratio.** "
    )
    return [
        "### What dominates these residuals",
        "",
        ratio + "A single national scalar converts accounting result into taxable "
        "profit. Fiscal result is not accounting result and no open source publishes "
        "the difference per firm. This one choice moves the IS line more than anything "
        "else in the model, which is exactly why the IS tolerance is not narrowed: a "
        "tighter gate would be an invitation to tune this number until the line goes "
        "green, and a margin spent that way can never be evidence again.",
        "",
        "**No loss carry-forward.** A real firm's deficits reduce its tax in later "
        "years; ours cannot, because carry-forward needs firm panels that are not open "
        "data. This biases simulated IS upward, mechanically.",
        "",
        "**No fiscal integration.** Groups are modelled as independent legal units, "
        "which over-counts firms at the reduced rate — a member of an intégration "
        "fiscale is not an IS payer at all, only the parent is.",
        "",
        "**No CFE.** It depends on communal valeur locative and thousands of local "
        "rates. A plausible-looking imitation would be worse than a declared hole.",
        "",
        f"**Within-cell dispersion is assumed, not published.** ESANE gives cell means "
        f"and totals, never quantiles, so the shape inside a cell is declared "
        f"(lognormal, sigma 1.4) rather than fitted. Every line whose residual depends "
        f"on where firms sit *within* a cell — the C3S abattement, the CVAE schedule, "
        f"the CEBGE thresholds — inherits that assumption. "
        f"{agg.share_zero_is:.1%} of firms pay no IS in this build.",
    ]


def render(
    agg: FirmAggregates,
    vintage: str,
    year: int = 2026,
    cells_are_synthetic: bool = True,
    fiscal_to_accounting: float | None = None,
    notes: list[str] | None = None,
) -> str:
    """The report, as markdown."""
    sources: dict[str, margins.Figure] = {}
    for use in ("calibration", "validation", "context"):
        sources.update(margins.figures_by_use(use))
    intro = INTRO if not cells_are_synthetic else SYNTHETIC_WARNING + "\n\n" + INTRO
    return reporting.render(
        title="Reconciliation report — entreprises",
        vintage=vintage,
        engine="openfisca-core 44.7.0 (système propre, hors openfisca-france)",
        intro=intro,
        lines=build_lines(agg, year),
        sources=sources,
        notes=(notes or []) + method_notes(agg, fiscal_to_accounting),
        generated_by="impots entreprises reconcile",
    )


def write(
    agg: FirmAggregates,
    vintage: str,
    year: int = 2026,
    cells_are_synthetic: bool = True,
    fiscal_to_accounting: float | None = None,
    notes: list[str] | None = None,
) -> Path:
    return reporting.write(
        REPORTS / "reconciliation_entreprises.md",
        render(agg, vintage, year, cells_are_synthetic, fiscal_to_accounting, notes),
    )
