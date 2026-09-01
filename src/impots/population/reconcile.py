"""The household population's reconciliation report (§5) — the credibility page.

Not internal QA. It states, line by line, how far the synthetic population's
simulated aggregates sit from published national totals, and which of those lines
were spent on calibration and therefore prove nothing.

The machinery — tolerance evaluation, the spent/validation split, take-up
bridges, formatting, the markdown itself — lives in `impots.reporting`, shared
with the firm report and tested there. This module only decides *which lines this
population has*, which is the part that is specific to households.
"""

from __future__ import annotations

from pathlib import Path

from impots import reporting
from impots.population import margins
from impots.population.aggregate import Aggregates

REPORTS = Path(__file__).resolve().parents[3] / "reports"

#: Declared tolerances (§5). Declared, not silently passed: a line outside its
#: tolerance is printed as such and the report says the population is not ready.
TOLERANCE = {"calibration": 0.02, "ir": 0.10, "benefit": 0.25, "distribution": 0.15}

Line = reporting.Line

INTRO = (
    "How far the synthetic population's simulated aggregates sit from published "
    "national totals. This page is the product, not an appendix: a distributional "
    "number is worth what this table says it is worth."
)


def build_lines(agg: Aggregates) -> list[Line]:
    """Every reconciliation line this population has, calibration and validation alike.

    `Line.from_figure` takes each line's `use` from the figure it came from, so a
    calibration target cannot be presented as validation — which is exactly what
    happened to the ménage count before raking existed.
    """
    totals = agg.totals
    lines: list[Line] = [
        Line.from_figure(
            margins.TOTAL_GROSS_WAGES, "Masse salariale brute",
            totals.get("salaire_brut"), TOLERANCE["calibration"],
            "Calibrated: the wage level was scaled to hit this. It proves the scaling "
            "worked, nothing more.",
            source="INSEE comptes nationaux (D11)",
        ),
        Line.from_figure(
            margins.DECLARED_PENSIONS, "Pensions et retraites", None,
            TOLERANCE["calibration"],
            "Calibrated: the pension mass was scaled to hit this.", source="DGFiP",
        ),
        Line.from_figure(
            margins.UNEMPLOYMENT_BENEFIT_SPEND, "Allocations chômage", None,
            TOLERANCE["calibration"],
            "Calibrated: the benefit mass was scaled to hit this.", source="Unédic",
        ),
        Line.from_figure(
            margins.IR_BAREME_ON_2024_INCOME, "Impôt sur le revenu — barème",
            totals.get("ir"), TOLERANCE["ir"],
            "The right comparator for this model: our households have none of the "
            "réductions et crédits d'impôt (19.5 bn) that separate the barème from the "
            "net yield, and no capital income.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.IR_NET_YIELD, "Impôt sur le revenu — recettes nettes",
            totals.get("ir"), TOLERANCE["ir"],
            "Shown for completeness and expected to be missed high: this figure is net "
            "of réductions/crédits and includes the PFU on capital income, neither of "
            "which the model has.",
            source="budget.gouv.fr",
        ),
        Line.from_figure(
            margins.DECLARED_WAGES, "Salaires déclarés (imposables)",
            totals.get("salaire_imposable"), TOLERANCE["ir"],
            "Semi-independent: the gross wage level is calibrated, so this tests the "
            "engine's gross-to-taxable transformation rather than the population.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.FOYERS_FISCAUX, "Foyers fiscaux",
            agg.counts.get("n_foyers"), TOLERANCE["ir"],
            "Structural, and one of the few lines untouched by the wage calibration: it "
            "depends on how the population was assembled into tax units, not on how "
            "much anybody earns.",
            source="DGFiP",
        ),
        Line.from_figure(
            margins.FOYERS_IMPOSES, "Foyers imposés",
            agg.counts.get("n_foyers_imposes"), TOLERANCE["ir"],
            "Depends on both the assembly and the income distribution near the tax "
            "threshold, so it is the sharpest available test of the middle of the "
            "synthetic wage distribution.",
            source="DGFiP",
        ),
    ]

    for key, label in (("af", "Allocations familiales"), ("ppa", "Prime d'activité"),
                       ("rsa", "RSA"), ("aide_logement", "Aides au logement")):
        figure = margins.BENEFIT_SPEND[key]
        bridge = margins.TAKE_UP_BRIDGE.get(key)
        simulated = totals.get(key)
        if bridge is None:
            lines.append(Line.from_figure(
                figure, label, simulated, TOLERANCE["benefit"],
                "No published take-up bridge for this benefit; judged on the flat ±25 % "
                "benefit tolerance.",
                source="CNAF / DREES",
            ))
            continue
        low, high = bridge
        centre = (low + high) / 2.0
        lines += reporting.bridge_lines(
            label, simulated, figure, bridge, TOLERANCE["benefit"],
            bridge_note=(
                f"Simulated entitlement divided by the mid-point of the take-up bridge "
                f"({centre:.2f}), which is what should be comparable with observed spend."
            ),
            raw_note=(
                f"OpenFisca computes legal entitlement, so this line *should* exceed "
                f"observed spend by a factor of {low:.2f}-{high:.2f} (DREES ER n° "
                f"1370/1379). Landing inside that band is the target; landing above it "
                f"means something other than non-take-up is at work."
            ),
            source="CNAF / DREES",
        )

    if agg.deciles:
        median = agg.deciles[4].mean_niveau_de_vie
        d1 = agg.deciles[0].mean_niveau_de_vie
        d9 = agg.deciles[8].mean_niveau_de_vie
        lines += [
            Line.from_figure(
                margins.NIVEAU_DE_VIE_MEDIAN, "Niveau de vie médian", median,
                TOLERANCE["distribution"],
                "Mean of decile 5, against the published median: close but not the same "
                "statistic. Filosofi is a 2023 vintage in 2023 euros.",
                source="INSEE Filosofi 2023",
            ),
            Line.from_figure(
                margins.NIVEAU_DE_VIE_D9_D1, "Rapport interdécile D9/D1",
                d9 / d1 if d1 else None, TOLERANCE["distribution"],
                "A pure shape statistic, unaffected by the wage level we calibrated — "
                "the most informative single line in this table.",
                source="INSEE Filosofi 2023",
            ),
        ]

    lines.append(Line.from_figure(
        margins.HOUSEHOLDS, "Ménages", agg.households, TOLERANCE["calibration"],
        "**Spent by raking (D-017).** Until raking existed this was a free check on the "
        "EEC weights; now the household-type margin sums to exactly this figure, so "
        "hitting it is the calibration working, not evidence about the model. The "
        "residual is what IPF's alternation between the two margin sets leaves behind.",
        source="INSEE recensement",
    ))
    return lines


def _comparison_note(sample: int | None) -> str:
    scale = (
        f"Both passes were run on a deterministic {sample:,} household ".replace(",", " ")
        + "subsample, and the selection is proportional to weight — so raking changes "
        "which households are drawn, not only how they are weighted. Aggregate sampling "
        "noise at this size is on the order of a point, which is larger than most of the "
        "shifts below."
        if sample
        else "Both passes were run over the full population, so the differences are the "
        "reweighting rather than sampling."
    )
    return "\n".join([
        "### What raking changed, and what it did not (D-017)",
        "",
        "The *Before raking* column is the same population built with `--no-raking`. "
        "Read it with two cautions.",
        "",
        f"**Small movements are noise.** {scale}",
        "",
        "**Raking fitted what it was aimed at and little else.** The ménage count goes "
        "to its target because that *is* the margin — it is calibrated, and spent. "
        "Everywhere else the effect is small and mixed in direction: the population's "
        "large residuals are a failure of income modelling, not of weighting, and no "
        "reweighting was ever going to close them (D-015). Reporting the lines that got "
        "worse alongside the ones that improved is the point of showing this column at all.",
    ])


def render(
    agg: Aggregates,
    vintage: str,
    notes: list[str] | None = None,
    unraked: Aggregates | None = None,
    sample: int | None = None,
) -> str:
    """The report, as markdown."""
    comparison = (
        {line.label: line.residual for line in build_lines(unraked)} if unraked else None
    )
    sources: dict[str, margins.Figure] = {}
    for use in ("calibration", "validation", "context"):
        sources.update(margins.figures_by_use(use))
    return reporting.render(
        title="Reconciliation report",
        vintage=vintage,
        engine="openfisca-france 176.0.8",
        intro=INTRO,
        lines=build_lines(agg),
        sources=sources,
        notes=notes,
        comparison=comparison,
        comparison_title="Before raking",
        comparison_note=_comparison_note(sample) if comparison else "",
        generated_by="impots population reconcile",
    )


def write(
    agg: Aggregates,
    vintage: str,
    notes: list[str] | None = None,
    unraked: Aggregates | None = None,
    sample: int | None = None,
) -> Path:
    return reporting.write(
        REPORTS / "reconciliation.md", render(agg, vintage, notes, unraked, sample)
    )
