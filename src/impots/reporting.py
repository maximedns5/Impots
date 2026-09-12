"""The shared reconciliation-report engine.

Extracted from `population/reconcile.py` before Phase 2 gave it a sibling
(PHASE2_SPEC §0.5 P1). The audit's reasoning: the module that generates the
project's credibility page had 345 untested lines and had already carried two
real defects, and the wrong move at that point is to copy it.

Both reports — households and firms — are the same object: a table of *simulated
against published*, split into lines that were spent on calibration and lines
that were not, each judged against a tolerance declared in advance.

## What this module enforces, rather than documents

**A figure used to calibrate can never appear as a validation line.** `Figure`
carries its own `use`, and `Line.from_figure` takes the use from the figure
rather than from the caller. `render` then refuses a report whose lines disagree
with their figures. In the population report this exact defect shipped: the
ménage count was presented as validation while raking targeted it — and against a
different vintage's value than the raking used, which flattered the residual to
+0.0 % when it was −0.8 %.

**Ratios and euro amounts do not share a formatter.** `format_value` renders
values below 100 with two decimals. The population report rendered an interdecile
ratio of 4.88 as "5" against a published 3.50 shown as "4", on the page whose
whole job is stating how far off the model is.

**No line is silently omitted.** A line with nothing to compare against is
rendered as "not modelled", never dropped. A table that quietly loses the lines
the model does badly on is worse than no table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

Use = Literal["calibration", "validation", "context"]

#: Below this, a value is a ratio or an index and wants decimals; above it, a
#: count or an amount and does not. The population report shipped without this
#: distinction and printed 4.88 as "5".
DECIMAL_BELOW = 100.0

#: A residual sitting exactly on its tolerance counts as within it.
#:
#: "±10 %" reads as inclusive, but `110e9 / 100e9 - 1` is 0.10000000000000009 in
#: binary floating point, so the exact boundary fails a naive comparison. Without
#: this slack a line whose residual prints as "+10.0%" against a "±10%" tolerance
#: can be marked OUTSIDE, and a reader would rightly conclude the report is
#: broken. The slack is far below the precision anything is reported to.
TOLERANCE_SLACK = 1e-9


class SpentMarginError(RuntimeError):
    """A line claims to validate something the model was calibrated to."""


@dataclass(frozen=True)
class Figure:
    """A published number, with everything needed to re-find and re-judge it.

    `use` is the load-bearing field. It is set where the figure is defined, next
    to its source, and travels with it into any report — so a figure cannot be
    tagged one way in the margins module and another way in the table.
    """

    value: float
    unit: str
    year: int
    scope: str
    source: str
    url: str
    use: Use
    caveat: str = ""


def figures_by_use(namespace: dict[str, Any], use: Use) -> dict[str, Figure]:
    """Every `Figure` in a module namespace declared with the given use.

    Reaches inside dicts as well, so `BENEFIT_SPEND["af"]` is found. Call as
    `figures_by_use(vars(margins), "validation")`.
    """
    found: dict[str, Figure] = {}
    for name, value in list(namespace.items()):
        if isinstance(value, Figure) and value.use == use:
            found[name] = value
        elif isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, Figure) and item.use == use:
                    found[f"{name}[{key}]"] = item
    return found


@dataclass
class Line:
    """One row of a reconciliation table."""

    label: str
    simulated: float | None
    published: float
    unit: str
    source: str
    use: Use
    tolerance: float
    note: str = ""
    figure_use: Use | None = None
    """The `use` of the figure this line came from, when it came from one.

    Kept separately so `render` can refuse a line whose own tagging has drifted
    away from its figure's — the defect that shipped in the population report.
    """
    population_year: int | None = None
    """The year of the population this line was simulated on, when it is not the
    comparator's own year.

    Set only by a trajectory: an UPRATED population is no longer calibrated, because
    every total on the spent side of the ledger was fitted to the base year. Comparing a
    2028 simulation to a 2024 published total is not a loose comparison, it is not a
    comparison at all — the two numbers are of different things. Leaving it None means
    «same year», which is every existing line and why they are unaffected."""
    comparator_year: int | None = None
    """The year the published figure describes. Paired with `population_year`."""

    raked_top_tail: bool = False
    """True when the population was raked onto DGFiP n° 41's fractiles (L1, D-121).

    **The rake SPENDS n° 41 and everything downstream of the income distribution's upper
    tail.** After it runs, the top IR lines fit the published fractiles by construction:
    they are calibration, not validation, and a tolerance verdict on them would report the
    rake working rather than the model being right.

    It is a separate field from `population_year` rather than folded into it because the
    two refusals have different reasons and a reader deserves to be told which applies. An
    uprated population is compared to the wrong YEAR; a raked one is compared to a figure
    it was fitted to.
    """

    @property
    def vintages_match(self) -> bool:
        """Whether this line compares two figures about the same year.

        Both None — the ordinary case — counts as matching: the reconciliation of a base
        year has always compared like with like and nothing here changes it.
        """
        if self.population_year is None or self.comparator_year is None:
            return True
        return self.population_year == self.comparator_year

    @classmethod
    def from_figure(
        cls,
        figure: Figure,
        label: str,
        simulated: float | None,
        tolerance: float,
        note: str = "",
        source: str | None = None,
    ) -> Line:
        """Build a line from a published figure, taking `use` from the figure.

        The only way to construct a line that cannot silently claim to validate a
        margin the model was fitted to.
        """
        return cls(
            label=label,
            simulated=simulated,
            published=figure.value,
            unit=figure.unit,
            source=source or figure.source,
            use=figure.use,
            tolerance=tolerance,
            note=note,
            figure_use=figure.use,
        )

    @property
    def residual(self) -> float | None:
        if self.simulated is None or self.published == 0:
            return None
        return self.simulated / self.published - 1.0

    @property
    def status(self) -> str:
        """What this line actually establishes.

        **"calibration" describes a line's USE, never its outcome**, and conflating the
        two printed a pass where no comparison had happened. The old version returned
        "calibrated (spent)" before looking at anything: a pension line that passes
        `None` as its simulated value — because no pension row is extracted at all —
        rendered as "Pensions et retraites | — | 400,4 bn € | calibrated (spent)" beside
        the note "the pension mass was scaled to hit this". That is the claim that a
        target was met, printed by a line that had compared nothing. And a calibration
        line missing its own target by 3.8 % against a ±1 % tolerance rendered the same
        way, and `passes` said True.

        So: absence of a comparison is reported first and as itself, and a calibration
        line that HAS a value is graded against its target like any other — being a
        calibration explains why hitting it proves little, not why missing it is fine.
        """
        if self.simulated is None:
            return "not modelled"
        if self.raked_top_tail:
            # Returns BEFORE any tolerance is evaluated, for the same reason the vintage
            # refusal below does: the line was fitted to this comparator, so a verdict
            # would read as validation while validating nothing. L1's completion condition.
            return "not comparable (queue recalée)"
        if not self.vintages_match:
            # A trajectory line: an uprated population against a base-year total. This
            # returns BEFORE any tolerance is evaluated, because a tolerance verdict here
            # would be read as validation and there is nothing being validated. F3 M2's
            # completion condition is exactly this refusal.
            return "not comparable (population vieillie)"
        residual = self.residual
        if residual is None:
            # `published == 0`: a relative residual against zero is not a large number,
            # it is not a number — the same reasoning the chiffrage harness applies
            # (D-095). The first version asserted it away and crashed on the first line
            # that legitimately targeted zero.
            return "not comparable (cible nulle)"
        within = abs(residual) <= self.tolerance * (1.0 + TOLERANCE_SLACK)
        if self.use == "calibration":
            return "calibrated (spent)" if within else "calibrated, OFF TARGET"
        return "within tolerance" if within else "OUTSIDE tolerance"

    @property
    def passes(self) -> bool:
        """A validation line must land inside tolerance; a calibration line must hit
        the target it was fitted to; a line that compared nothing passes nothing.

        The last two clauses are new. A calibration that misses is a broken fit, not a
        licence — and "not modelled" was previously indistinguishable from success on a
        calibration line, because the calibration branch returned before looking.
        """
        return self.status in ("within tolerance", "calibrated (spent)") or (
            self.use == "context")


#: The French thousands separator, written as an escape: a literal narrow no-break space
#: is invisible in a diff and indistinguishable from an ordinary one.
THIN_SPACE = "\u202f"


def num_fr(value: float, decimals: int = 0) -> str:
    """A number in French typography — and ONLY the number.

    Order matters: Python writes «1,234.56», French wants «1 234,56». Swapping in place
    would turn the thousands comma into a second decimal comma and give «1 234 56».

    Lives here rather than in each renderer because it was written twice already — once
    in `fiche` and once, worse, in a first draft of `uprating` that printed «+2.5%» in a
    French document. A formatter duplicated is a formatter that diverges.
    """
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", THIN_SPACE)


def pct_fr(value: float, decimals: int = 0) -> str:
    """A percentage in French typography: comma decimal, narrow space before the sign.

    Python's `:.0%` gives «22%». French sets «22 %».

    Zero decimals by default because most call sites want «22 %» rather than «22,0 %»;
    a caller wanting decimals asks for them. The default matters: moving it from 0 to 1
    silently reworded every percentage in the fiche, which two tests caught.
    """
    return num_fr(value * 100, decimals) + THIN_SPACE + "%"


def format_value(value: float | None, unit: str) -> str:
    """Render a value for a report table.

    Values below `DECIMAL_BELOW` keep two decimals: they are ratios, and rounding
    a ratio of 4.88 to "5" against a published "4" misstates the very thing the
    report exists to state.

    **Euros are scaled to their magnitude, and they did not use to be.** This
    formatter assumed "the reports deal in national aggregates and nothing else",
    which stopped being true when the ISF-2017 backtest added PER-HOUSEHOLD lines:
    a published mean of 25 821 EUR rendered as "0.0 bn €", on the page whose whole
    job is saying how far the model is from its target. Same class as the
    interdecile ratio that printed "5" against a published "4" — a formatter whose
    assumption about its input had quietly expired.
    """
    if value is None:
        return "—"
    if unit == "EUR":
        if abs(value) >= 1e9:
            return f"{value / 1e9:,.1f} bn €".replace(",", " ")
        if abs(value) >= 1e6:
            return f"{value / 1e6:,.1f} M €".replace(",", " ")
        return f"{value:,.0f} €".replace(",", " ")
    if unit == "count":
        return f"{value / 1e6:,.2f} M".replace(",", " ")
    if abs(value) < DECIMAL_BELOW:
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:,.0f}".replace(",", " ")


def format_residual(residual: float | None) -> str:
    return "—" if residual is None else f"{residual:+.1%}"


def bridge_lines(
    label: str,
    simulated: float | None,
    figure: Figure,
    bridge: tuple[float, float],
    flat_tolerance: float,
    bridge_note: str,
    raw_note: str,
    source: str | None = None,
) -> list[Line]:
    """A benefit judged twice: against its take-up bridge, and raw.

    A model computing legal entitlement is not comparable with observed spend
    without knowing how much of the entitlement is never claimed. The bridge is
    the ratio of eligible mass to mass actually paid — **not** the non-take-up
    rate, which is computed over a different denominator and is the natural
    number to reach for and get wrong.

    Both lines are emitted because both are true and they can disagree: a benefit
    can sit inside a flat tolerance raw while being well below where a
    full-take-up model should put it.
    """
    low, high = bridge
    centre = (low + high) / 2.0
    return [
        Line.from_figure(
            figure,
            f"{label} (bridge-adjusted)",
            None if simulated is None else simulated / centre,
            (high - low) / 2.0 / centre + 0.10,
            bridge_note,
            source,
        ),
        Line.from_figure(figure, label, simulated, flat_tolerance, raw_note, source),
    ]


def _check_tagging(lines: list[Line]) -> None:
    """Refuse a report whose lines disagree with their own figures."""
    drifted = [
        line.label
        for line in lines
        if line.figure_use is not None and line.figure_use != line.use
    ]
    if drifted:
        raise SpentMarginError(
            "these lines are tagged differently from the figures they came from, "
            f"which is how a calibration target gets presented as evidence: {drifted}"
        )


def render(
    *,
    title: str,
    vintage: str,
    engine: str,
    intro: str,
    lines: list[Line],
    sources: dict[str, Figure],
    notes: list[str] | None = None,
    comparison: dict[str, float | None] | None = None,
    comparison_title: str = "",
    comparison_note: str = "",
    generated_by: str = "",
) -> str:
    """The whole report, as markdown.

    `comparison` maps a line label to its residual under some alternative build —
    an extra column, always showing every line including the ones that moved the
    wrong way.
    """
    _check_tagging(lines)

    calibration = [line for line in lines if line.use == "calibration"]
    validation = [line for line in lines if line.use == "validation"]
    failing = [line for line in validation if line.status == "OUTSIDE tolerance"]

    out: list[str] = [
        f"# {title}",
        "",
        f"**Vintage**: `{vintage}` · **Generated**: {date.today().isoformat()}"
        + (f" by `{generated_by}`" if generated_by else "")
        + f" · **Engine**: {engine}",
        "",
        intro,
        "",
        "## The rule that makes this table mean something",
        "",
        "A figure used to **calibrate** is *spent*. The model was tuned to hit it, so "
        "hitting it is evidence of nothing except that the tuning ran. Those lines are "
        "listed separately and are never counted as validation. Everything in the "
        "validation table below was **not** tuned to.",
        "",
        "## Calibration targets (spent)",
        "",
        "| Line | Simulated | Published | Residual | Source |",
        "|---|---:|---:|---:|---|",
    ]
    for line in calibration:
        out.append(
            f"| {line.label} | {format_value(line.simulated, line.unit)} | "
            f"{format_value(line.published, line.unit)} | "
            f"{format_residual(line.residual)} | {line.source} |"
        )

    extra_head = f" {comparison_title} |" if comparison else ""
    extra_rule = " ---: |" if comparison else ""
    out += [
        "",
        "## Validation lines (untouched by calibration)",
        "",
        f"| Line | Simulated | Published |{extra_head} Residual | Tolerance | Status | Source |",
        f"|---|---:|---:|{extra_rule}---:|---:|---|---|",
    ]
    for line in validation:
        was = ""
        if comparison is not None:
            was = f" {format_residual(comparison.get(line.label))} |"
        out.append(
            f"| {line.label} | {format_value(line.simulated, line.unit)} | "
            f"{format_value(line.published, line.unit)} |{was} "
            f"{format_residual(line.residual)} | ±{line.tolerance:.0%} | "
            f"{line.status} | {line.source} |"
        )

    if comparison is not None and comparison_note:
        out += ["", comparison_note]

    described = [line for line in lines if line.note]
    if described:
        out += ["", "### What each line means", ""]
        out += [f"* **{line.label}** — {line.note}" for line in described]

    out += ["", "## Verdict", ""]
    if failing:
        out += [
            f"**{len(failing)} validation line(s) outside declared tolerance**: "
            + ", ".join(
                f"{line.label} ({format_residual(line.residual)})" for line in failing
            ),
            "",
            "These are stated, not smoothed over. The known causes are listed below; "
            "none of them is fixed by tuning, and tuning to close them would spend the "
            "very lines that make this table worth reading.",
        ]
    else:
        out.append("Every validation line is within its declared tolerance.")

    if notes:
        out += ["", "## Known limitations", ""]
        out += [f"* {note}" for note in notes]

    out += [
        "",
        "## Sources",
        "",
        "| Figure | Year | Scope | Source |",
        "|---|---|---|---|",
    ]
    for name, figure in sorted(sources.items()):
        out.append(
            f"| `{name}` | {figure.year} | {figure.scope} | "
            f"[{figure.source}]({figure.url}) |"
        )
    return "\n".join(out) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
