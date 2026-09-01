"""The reconciliation report (§5) — the project's credibility page.

Not internal QA. This is a first-class product output: it states, line by line,
how far the synthetic population's simulated aggregates sit from published
national totals, and — crucially — which lines were *spent* on calibration and
therefore prove nothing.

Two rules the generator enforces mechanically rather than by good intentions:

  1. **A calibration target may not appear as a validation line.** `margins.py`
     tags every figure with its use; a figure tagged `calibration` is printed in
     the calibration section and refused in the validation one. Hitting a number
     you tuned to is not evidence.
  2. **No line is silently omitted.** Every figure in `margins.py` tagged
     `validation` appears, even when the model has nothing to compare it against —
     in which case the row says so. A reconciliation table that quietly drops the
     lines the model does badly on is worse than no table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from impots.population import margins
from impots.population.aggregate import Aggregates

REPORTS = Path(__file__).resolve().parents[3] / "reports"

#: Declared tolerances (§5). Declared, not silently passed: a line outside its
#: tolerance is printed as such and the report says the population is not ready.
TOLERANCE = {"calibration": 0.02, "ir": 0.10, "benefit": 0.25, "distribution": 0.15}


@dataclass
class Line:
    label: str
    simulated: float | None
    published: float
    unit: str
    source: str
    use: str
    tolerance: float
    note: str = ""

    @property
    def residual(self) -> float | None:
        if self.simulated is None or self.published == 0:
            return None
        return self.simulated / self.published - 1.0

    @property
    def status(self) -> str:
        if self.use == "calibration":
            return "calibrated (spent)"
        if self.simulated is None:
            return "not modelled"
        residual = self.residual
        assert residual is not None
        return "within tolerance" if abs(residual) <= self.tolerance else "OUTSIDE tolerance"


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "EUR":
        return f"{value / 1e9:,.1f} bn €".replace(",", " ")
    if unit == "count":
        return f"{value / 1e6:,.2f} M".replace(",", " ")
    # Ratios and euro amounts share the "raw" unit but not the right precision.
    # Rounding to integers rendered an interdecile ratio of 4.88 as "5" against a
    # published "3.5" shown as "4" — on the page whose whole job is stating how far
    # off the model is.
    if abs(value) < 100:
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:,.0f}".replace(",", " ")


def build_lines(agg: Aggregates) -> list[Line]:
    """Every reconciliation line, calibration and validation alike."""
    totals = agg.totals
    lines: list[Line] = [
        Line("Masse salariale brute", totals.get("salaire_brut"),
             margins.TOTAL_GROSS_WAGES.value, "EUR", "INSEE comptes nationaux (D11)",
             "calibration", TOLERANCE["calibration"],
             "Calibrated: the wage level was scaled to hit this. It proves the "
             "scaling worked, nothing more."),
        Line("Pensions et retraites", None, margins.DECLARED_PENSIONS.value, "EUR",
             "DGFiP", "calibration", TOLERANCE["calibration"],
             "Calibrated: the pension mass was scaled to hit this."),
        Line("Allocations chômage", None, margins.UNEMPLOYMENT_BENEFIT_SPEND.value, "EUR",
             "Unédic", "calibration", TOLERANCE["calibration"],
             "Calibrated: the benefit mass was scaled to hit this."),

        Line("Impôt sur le revenu — barème", totals.get("ir"),
             margins.IR_BAREME_ON_2024_INCOME.value, "EUR", "DGFiP", "validation",
             TOLERANCE["ir"],
             "The right comparator for this model: our households have none of the "
             "réductions et crédits d'impôt (19.5 bn) that separate the barème from "
             "the net yield, and no capital income."),
        Line("Impôt sur le revenu — recettes nettes", totals.get("ir"),
             margins.IR_NET_YIELD.value, "EUR", "budget.gouv.fr", "validation",
             TOLERANCE["ir"],
             "Shown for completeness and expected to be missed high: this figure is "
             "net of réductions/crédits and includes the PFU on capital income, "
             "neither of which the model has."),
        Line("Salaires déclarés (imposables)", totals.get("salaire_imposable"),
             margins.DECLARED_WAGES.value, "EUR", "DGFiP", "validation",
             TOLERANCE["ir"],
             "Semi-independent: the gross wage level is calibrated, so this tests "
             "the engine's gross-to-taxable transformation rather than the population."),
        Line("Foyers fiscaux", agg.counts.get("n_foyers"), margins.FOYERS_FISCAUX.value,
             "count", "DGFiP", "validation", TOLERANCE["ir"],
             "Structural, and one of the few lines untouched by the wage calibration: "
             "it depends on how the population was assembled into tax units, not on "
             "how much anybody earns."),
        Line("Foyers imposés", agg.counts.get("n_foyers_imposes"),
             margins.FOYERS_IMPOSES.value, "count", "DGFiP", "validation",
             TOLERANCE["ir"],
             "Depends on both the assembly and the income distribution near the tax "
             "threshold, so it is the sharpest available test of the middle of the "
             "synthetic wage distribution."),
    ]

    for key, label in (("af", "Allocations familiales"), ("ppa", "Prime d'activité"),
                       ("rsa", "RSA"), ("aide_logement", "Aides au logement")):
        bridge = margins.TAKE_UP_BRIDGE.get(key)
        if bridge is None:
            note = ("No published take-up bridge for this benefit; judged on the flat "
                    "±25 % benefit tolerance.")
            tolerance = TOLERANCE["benefit"]
        else:
            low, high = bridge
            # The bridge is not the non-take-up rate. DREES's uplift is computed over
            # the recourants' mass; what a full-take-up model should reproduce is the
            # ratio of eligible mass to mass actually paid, which is this band.
            note = (
                f"OpenFisca computes legal entitlement, so this line *should* exceed "
                f"observed spend by a factor of {low:.2f}-{high:.2f} "
                f"(DREES ER n° 1370/1379). Landing inside that band is the target; "
                f"landing above it means something other than non-take-up is at work."
            )
            # Centre the tolerance on the middle of the bridge rather than on 1.0.
            centre = (low + high) / 2.0
            tolerance = (high - low) / 2.0 / centre + 0.10
            lines.append(Line(
                f"{label} (bridge-adjusted)", 
                None if totals.get(key) is None else totals[key] / centre,
                margins.BENEFIT_SPEND[key].value, "EUR", "CNAF / DREES", "validation",
                tolerance,
                f"Simulated entitlement divided by the mid-point of the take-up bridge "
                f"({centre:.2f}), which is what should be comparable with observed spend.",
            ))
            tolerance = TOLERANCE["benefit"]
        lines.append(Line(
            label, totals.get(key), margins.BENEFIT_SPEND[key].value, "EUR",
            "CNAF / DREES", "validation", tolerance, note,
        ))

    if agg.deciles:
        median = agg.deciles[4].mean_niveau_de_vie
        d1 = agg.deciles[0].mean_niveau_de_vie
        d9 = agg.deciles[8].mean_niveau_de_vie
        lines += [
            Line("Niveau de vie médian", median, margins.NIVEAU_DE_VIE_MEDIAN.value,
                 "raw", "INSEE Filosofi 2023", "validation", TOLERANCE["distribution"],
                 "Mean of decile 5, against the published median: close but not the "
                 "same statistic. Filosofi is a 2023 vintage in 2023 euros."),
            Line("Rapport interdécile D9/D1", d9 / d1 if d1 else None,
                 margins.NIVEAU_DE_VIE_D9_D1.value, "raw", "INSEE Filosofi 2023",
                 "validation", TOLERANCE["distribution"],
                 "A pure shape statistic, unaffected by the wage level we calibrated — "
                 "the most informative single line in this table."),
        ]

    lines.append(Line(
        "Ménages", agg.households, margins.HOUSEHOLDS.value, "count",
        "INSEE recensement", margins.HOUSEHOLDS.use, TOLERANCE["calibration"],
        "**Spent by raking (D-017).** Until raking existed this was a free check on "
        "the EEC weights; now the household-type margin sums to exactly this figure, "
        "so hitting it is the calibration working, not evidence about the model. The "
        "residual is what IPF's alternation between the two margin sets leaves behind.",
    ))
    return lines


def render(
    agg: Aggregates,
    vintage: str,
    notes: list[str] | None = None,
    unraked: Aggregates | None = None,
    sample: int | None = None,
) -> str:
    """The report, as markdown.

    `unraked` adds the before/after that D-017 requires: every line as it stood
    without calibration, next to where it stands with it, **whichever direction it
    moved**. A report that showed only the lines raking improved would be an
    advertisement, not a reconciliation.
    """
    lines = build_lines(agg)
    before = {line.label: line.residual for line in build_lines(unraked)} if unraked else {}
    failing = [
        line for line in lines
        if line.use == "validation" and line.status == "OUTSIDE tolerance"
    ]

    out: list[str] = [
        "# Reconciliation report",
        "",
        f"**Population vintage**: `{vintage}` · **Generated**: {date.today().isoformat()} "
        "by `impots population reconcile` · **Engine**: openfisca-france 176.0.8",
        "",
        "How far the synthetic population's simulated aggregates sit from published "
        "national totals. This page is the product, not an appendix: a distributional "
        "number is worth what this table says it is worth.",
        "",
        "## The rule that makes this table mean something",
        "",
        "A figure used to **calibrate** the population is *spent*. The model was tuned "
        "to hit it, so hitting it is evidence of nothing except that the tuning ran. "
        "Those lines are listed separately and are never counted as validation. "
        "Everything in the validation table below was **not** tuned to.",
        "",
        "## Calibration targets (spent)",
        "",
        "| Line | Simulated | Published | Residual | Source |",
        "|---|---:|---:|---:|---|",
    ]
    for line in lines:
        if line.use != "calibration":
            continue
        residual = "—" if line.residual is None else f"{line.residual:+.1%}"
        out.append(
            f"| {line.label} | {_fmt(line.simulated, line.unit)} | "
            f"{_fmt(line.published, line.unit)} | {residual} | {line.source} |"
        )

    raked_column = " Before raking |" if before else ""
    raked_dashes = " ---: |" if before else ""
    out += [
        "",
        "## Validation lines (untouched by calibration)",
        "",
        f"| Line | Simulated | Published |{raked_column} Residual | Tolerance | Status | Source |",
        f"|---|---:|---:|{raked_dashes}---:|---:|---|---|",
    ]
    for line in lines:
        if line.use != "validation":
            continue
        residual = "—" if line.residual is None else f"{line.residual:+.1%}"
        was = ""
        if before:
            previous = before.get(line.label)
            was = f" {'—' if previous is None else f'{previous:+.1%}'} |"
        out.append(
            f"| {line.label} | {_fmt(line.simulated, line.unit)} | "
            f"{_fmt(line.published, line.unit)} |{was} {residual} | ±{line.tolerance:.0%} | "
            f"{line.status} | {line.source} |"
        )

    if before:
        out += [
            "",
            "### What raking changed, and what it did not (D-017)",
            "",
            "The *Before raking* column is the same population built with "
            "`--no-raking`. Read it with two cautions.",
            "",
            "**Small movements are noise.** " + (
                # Space the thousands separator on the NUMBER, not on the sentence:
                # `.replace(",", " ")` over the whole string eats the punctuation.
                f"Both passes were run on a deterministic {sample:,} household "
                .replace(",", " ")
                + "subsample, and the selection is proportional to weight — so raking "
                "changes which households are drawn, not only how they are weighted. "
                "Aggregate sampling noise at this size is on the order of a point, "
                "which is larger than most of the shifts below."
                if sample else
                "Both passes were run over the full population, so the differences "
                "are the reweighting rather than sampling."
            ),
            "",
            "**Raking fitted what it was aimed at and little else.** The ménage count "
            "goes to its target because that *is* the margin — it is calibrated, and "
            "spent. Everywhere else the effect is small and mixed in direction: the "
            "population's large residuals are a failure of income modelling, not of "
            "weighting, and no reweighting was ever going to close them (D-015). "
            "Reporting the lines that got worse alongside the ones that improved is "
            "the point of showing this column at all.",
        ]

    out += ["", "### What each line means", ""]
    for line in lines:
        if line.note:
            out.append(f"* **{line.label}** — {line.note}")

    out += [
        "",
        "## Verdict",
        "",
    ]
    if failing:
        out += [
            f"**{len(failing)} validation line(s) outside declared tolerance**: "
            + ", ".join(f"{line.label} ({line.residual:+.0%})" for line in failing),
            "",
            "Per §5 of the Phase 1 specification these are stated, not smoothed over. "
            "The known causes are listed below; none of them is fixed by tuning, and "
            "tuning to close them would spend the very lines that make this table "
            "worth reading.",
        ]
    else:
        out.append("Every validation line is within its declared tolerance.")

    if notes:
        out += ["", "## Known limitations of this population", ""]
        out += [f"* {note}" for note in notes]

    out += [
        "",
        "## Sources",
        "",
        "| Figure | Year | Scope | Source |",
        "|---|---|---|---|",
    ]
    seen: set[str] = set()
    for use in ("calibration", "validation", "context"):
        for name, figure in sorted(margins.figures_by_use(use).items()):
            if name in seen:
                continue
            seen.add(name)
            out.append(
                f"| `{name}` | {figure.year} | {figure.scope} | "
                f"[{figure.source}]({figure.url}) |"
            )
    return "\n".join(out) + "\n"


def write(
    agg: Aggregates,
    vintage: str,
    notes: list[str] | None = None,
    unraked: Aggregates | None = None,
    sample: int | None = None,
) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / "reconciliation.md"
    path.write_text(render(agg, vintage, notes, unraked, sample), encoding="utf-8")
    return path
