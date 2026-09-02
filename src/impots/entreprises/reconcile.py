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


def build_lines(
    agg: FirmAggregates, year: int, turnover_vintage: int | None = None
) -> list[Line]:
    """Every reconciliation line this population has, calibration and validation alike."""
    totals = agg.totals
    c3s_figure, c3s_why = margins.c3s_for_turnover_year(turnover_vintage)
    lines: list[Line] = [
        Line.from_figure(
            margins.TAXABLE_PROFIT, "Bénéfice imposable total",
            agg.taxable_profit, TOLERANCE["calibration"],
            "**Spent, and it is the most consequential spend in this table.** The cell "
            "table's fiscal-to-accounting ratio is computed to reproduce this total, so "
            "hitting it is arithmetic. Everything the IS level does downstream inherits "
            "that — see the next line.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.IS_AVANT_CREDITS, "Impôt sur les sociétés",
            totals.get("impot_societes"), TOLERANCE["is"],
            "**The level of this line is calibrated and the rate is not.** The taxable "
            "profit above is reproduced by construction, and IS is roughly a quarter of "
            "it, so landing near the published total is most of the way guaranteed. What "
            "this line still tests is whether applying the real schedule — the 15 % slice, "
            "its ceilings, its eligibility — to a *synthetic distribution* of a correct "
            "total lands where the published tax does. That test is the line below, and it "
            "is the one to read. Biased upward by the absence of loss carry-forward.",
            source="INSEE comptes nationaux",
        ),
        Line.from_figure(
            margins.AVERAGE_RATE_ON_PROFITS, "Taux moyen d'IS sur les bénéfices",
            (totals.get("impot_societes") or 0.0) / agg.taxable_profit
            if agg.taxable_profit else None,
            TOLERANCE["shape"],
            "**The free test, and the one the module should be judged on.** Total IS "
            "over total taxable profit. The denominator is calibrated and the numerator "
            "is not: it comes from applying the statutory schedule to a synthetic "
            "distribution that nothing pinned. If the distribution were wrong — too many "
            "firms in the 15 % slice, too few above it — this rate would miss even though "
            "the level above did not.",
            source="DGFiP",
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
            c3s_figure, "C3S", totals.get("c3s"), TOLERANCE["instrument"],
            "The cleanest line in the table: the base is turnover, which is calibrated per "
            "cell, and the rate is a flat 0.16 % above a 19 M€ abattement. A residual here "
            "is almost entirely the distribution of turnover *within* cells — the one thing "
            "in the population that no published source constrains. " + c3s_why + " The "
            "sectoral caps for banks and commissionnaires are still not modelled.",
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

    if agg.cells:
        by_section: dict[str, float] = {}
        for cell in agg.cells:
            by_section[cell.naf_section] = by_section.get(cell.naf_section, 0.0) + cell.is_brut
        for label, (published, sections) in margins.IS_BRUT_BY_SECTOR.items():
            simulated = sum(by_section.get(section, 0.0) for section in sections)
            covered = [section for section in sections if section in by_section]
            if not covered:
                continue
            missing = [section for section in sections if section not in by_section]
            note = (
                f"NAF {'+'.join(sections)}. One of the module's few genuinely free "
                f"lines: the sector shape is Ésane's and the calibration is national and "
                f"by size class, so nothing was fitted to this."
            )
            if missing:
                note += (
                    f" Sections {'+'.join(missing)} are absent from the population "
                    f"(Ésane suppressed their values), so this line is short by whatever "
                    f"they contribute and is expected to be missed low."
                )
            lines.append(Line.from_figure(
                margins.is_sector_figure(label, published),
                f"IS — {label}", simulated, TOLERANCE["is"], note, source="DGFiP",
            ))

    if agg.by_size:
        by_size = {row.taille: row for row in agg.by_size}
        weighted = sum(row.mean_effective_rate * row.n_firms for row in agg.by_size)
        firms = sum(row.n_firms for row in agg.by_size)
        lines.append(Line(
            label="Taux effectif moyen (moyenne par entreprise)",
            simulated=weighted / firms if firms else None,
            published=margins.AVERAGE_RATE_ON_PROFITS.value,
            unit="ratio", source="DGFiP Stat 39", use="context",
            tolerance=TOLERANCE["shape"],
            note="Context, because it is not the same statistic as the published one and "
                 "never was. This averages a *rate per firm* over all firms, so France's "
                 "two and a half million micro-enterprises dominate it; DGFiP's figure is "
                 "profit-weighted, so a few thousand large firms dominate that. The "
                 "like-for-like comparison is the aggregate rate line above, which lands "
                 "inside tolerance. Printed rather than dropped because it is the number a "
                 "reader would otherwise compute themselves from the by-size table.",
            figure_use="context",
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


def _vintage_year(vintage: str) -> int | None:
    """The population's turnover year, when the vintage names one."""
    return int(vintage) if vintage.isdigit() and len(vintage) == 4 else None


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
        lines=build_lines(agg, year, _vintage_year(vintage)),
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
