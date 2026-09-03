"""Reading the IMK multiplier meta-regressions (M1, the fan's width).

Mésange gives this project a central value per instrument per horizon, from an official
French model. What it cannot give is a *band*: it publishes no confidence interval, and
its own sensitivity analysis is degenerate at one year — 1.31 for public investment
under all four of its hypothesis sets. A width taken from it would be an artefact of a
model that is deterministic in the short run by construction.

The credible width is cross-study dispersion, and these two meta-analyses measure it:

* **WP117** (Gechert 2013) — 104 studies, 1 069 reported multipliers, dispersion by
  fiscal impulse and by model class;
* **WP139** (Gechert and Rannenberg 2014) — 98 studies, 1 882 observations, the same
  broken out by *regime*, which is the only sourced answer this repo has to what a
  multiplier becomes in a downturn.

**Parsed, never transcribed** (D-026), same as `mesange`.

THE SCOPE PROBLEM, STATED UP FRONT, because it is the thing to attack: the standard
deviations below are dispersion *across studies* — different countries, horizons,
identification strategies and model classes. Gechert's own conclusion is that "reported
multipliers vary with study-design". They are therefore NOT the sampling error of one
country's multiplier at one horizon, and using them as such overstates genuine
uncertainty about France. Any row resting on them says so.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"

#: The statistic rows each descriptive table prints, keyed by the label used here.
#: "Std.Dev" and "Std. dev." are the same row: WP139's third block drops the space,
#: and a parser matching one spelling silently loses a block.
STAT_LABELS = {
    "mean": ("Mean",),
    "median": ("Median",),
    "sd": ("Std. dev.", "Std.Dev", "Std. Dev.", "Std.dev."),
    "maximum": ("Max",),
    "minimum": ("Min",),
    "n": ("N",),
}

#: Column headers, per document. A header line is recognised by being made ENTIRELY of
#: these tokens — the tables carry no other structure a parser could key on, and
#: guessing from position is how the TES read two totals out of one column.
COLUMNS = {
    "wp117": {
        "TOTAL", "GSPEND", "TRANS", "TAX", "DEFICIT",
        "SPEND", "CONS", "INVEST", "MILIT", "EMPLOY",
        "DSGE-NK", "RBC", "MACRO", "SEE", "VAR",
    },
    "wp139": {
        "TOTAL", "SPEND", "CONS", "INVEST", "MILIT",
        "TAX", "TRANS", "DEF",
        "SEE", "VAR", "RAV", "RUP", "RLO",
    },
}

DOCUMENTS = {
    "wp117": "imk_wp117_2013_gechert_meta_regression.pdf",
    "wp139": "imk_wp139_2014_gechert_rannenberg_regime_dependent.pdf",
}

#: What the regime columns of WP139 mean. Spelled out because "RLO" is the single most
#: consequential three letters in this file: it is the downturn multiplier, and the
#: spec's unsourced "1.3-2.5 in slack" seed lands next to it.
REGIMES = {
    "RAV": "toutes phases confondues — l'étude ne distingue pas le régime",
    "RUP": "haut de cycle",
    "RLO": "bas de cycle",
}


class ImkError(RuntimeError):
    """A meta-analysis table cannot be read as expected."""


@dataclass(frozen=True)
class Stats:
    """One column of a descriptive table."""

    column: str
    document: str
    mean: float
    median: float
    sd: float
    maximum: float
    minimum: float
    n: int

    @property
    def coefficient_of_variation(self) -> float:
        """Dispersion relative to the central value.

        The honest summary of these tables: for tax-side multipliers the standard
        deviation EXCEEDS the mean. That is the property the L4 banner is describing,
        and it is stronger than the "facteur 3 à 5" the copy proposes.
        """
        if self.mean == 0:
            raise ImkError(f"{self.column}: a mean of zero has no coefficient of variation")
        return abs(self.sd / self.mean)


def _normalise(line: str) -> str:
    # The extractor renders the fi/fl ligatures as single codepoints.
    return " ".join(line.replace("ﬁ", "fi").replace("ﬂ", "fl").split())


def _floats(tail: str) -> list[float]:
    return [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", tail)]


@lru_cache(maxsize=4)
def _lines(path: str) -> tuple[str, ...]:
    import pypdf

    return tuple(
        _normalise(line)
        for page in pypdf.PdfReader(path).pages
        for line in (page.extract_text() or "").splitlines()
    )


def load(document: str, raw: Path | None = None) -> dict[str, Stats]:
    """Every descriptive-statistics column of one meta-analysis.

    Raises rather than returning a partial table: a block silently lost to a spelling
    variant would leave a column missing, and a caller asking for it would get a
    KeyError far from the cause.
    """
    if document not in DOCUMENTS:
        raise ImkError(f"unknown document {document!r}; have {sorted(DOCUMENTS)}")
    path = (raw or RAW) / DOCUMENTS[document]
    if not path.exists():
        raise ImkError(f"{path} not found — download it and record it in the manifest")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise ImkError("pypdf is required to read the IMK working papers")

    known = COLUMNS[document]
    stats: dict[str, Stats] = {}
    lines = _lines(str(path))
    for index, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) < 3 or not all(token in known for token in tokens):
            continue
        block = _block(lines[index + 1: index + 12], tokens, document)
        # Later blocks repeat no column, so a duplicate means the header matched
        # something that was not a header.
        for column, values in block.items():
            stats.setdefault(column, values)
    missing = known - set(stats)
    if missing:
        raise ImkError(
            f"{document}: no descriptive block found for {sorted(missing)}. The paper "
            f"may have been revised — do not fall back to a neighbouring column."
        )
    return stats


def _block(following: tuple[str, ...], columns: list[str], document: str) -> dict[str, Stats]:
    rows: dict[str, list[float]] = {}
    for line in following:
        for key, labels in STAT_LABELS.items():
            label = next((lab for lab in labels if line.startswith(lab)), None)
            if label is None or key in rows:
                continue
            values = _floats(line[len(label):])
            if len(values) == len(columns):
                rows[key] = values
    if set(rows) != set(STAT_LABELS):
        return {}
    return {
        column: Stats(
            column=column, document=document,
            mean=rows["mean"][i], median=rows["median"][i], sd=rows["sd"][i],
            maximum=rows["maximum"][i], minimum=rows["minimum"][i], n=int(rows["n"][i]),
        )
        for i, column in enumerate(columns)
    }


#: These tables have no horizon dimension at all: a meta-analysis pools estimates made
#: at whatever horizon each primary study chose. Saying so with an explicit single
#: "all" is better than inventing years the source does not carry.
HORIZONS = ("all",)


def table(row: str, document: str = "wp117",
          raw: Path | None = None) -> tuple[dict[str, tuple[float, ...]], tuple[str, ...]]:
    """One statistic across every column, as (values by column, horizons).

    `row` names an attribute of `Stats`, so a derived quantity like
    `coefficient_of_variation` is addressable without being stored — it is computed by
    the same reviewed code that parsed the table it comes from.
    """
    stats = load(document, raw=raw)
    try:
        return {column: (float(getattr(value, row)),) for column, value in stats.items()}, HORIZONS
    except AttributeError as error:
        raise ImkError(
            f"{document}: no statistic {row!r} on a descriptive column; "
            f"have mean, median, sd, maximum, minimum, n, coefficient_of_variation"
        ) from error
