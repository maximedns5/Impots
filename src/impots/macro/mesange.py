"""Reading the Mésange variant tables (M1).

Mésange is the quarterly macroeconometric model of the French economy maintained
jointly by INSEE and the DG Trésor. Its section 4, "Principales variantes", publishes
the response of the economy to a 1-point-of-GDP shock on each budgetary instrument,
at 1, 2, 3, 5 and 10 years and in the long run — GDP, employment, consumption,
household income and the primary balance.

That is the multiplier evidence this project needs, from an official French source,
instrument by instrument, with the horizon profile attached rather than assumed.

**The numbers are parsed from the PDF, never transcribed.** D-026: calibration inputs
are computed from the primary file by tested code, because a figure that passes through
a human's or an agent's retyping has been measured twice failing. The YAML alongside
carries scope, support and verdicts — never a value.

One property of the source that must travel with every number it yields: Mésange is a
**linear** model. It has no cycle state, so it cannot answer what a multiplier becomes
in a slump, and the sign conventions below assume a symmetry the model imposes by
construction rather than one anybody measured.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"

SOURCE_FILE = "insee_G2017-04_mesange.pdf"

#: Horizons, in the column order the tables print them. "LT" is the model's long-run
#: equilibrium, not a year, and is kept under its own name rather than given a number.
HORIZONS = ("1", "2", "3", "5", "10", "LT")

#: The rows worth reading, keyed by the label each table prints in its left column.
ROWS = {
    "gdp": "PIB en volume",
    "consommation": "Consommation des ménages",
    "investissement_entreprises": "Investissement des SNF et EI",
    "revenu_disponible": "Revenu disponible réel des ménages",
    "emploi_milliers": "Emploi salarié marchand (en milliers)",
    "solde_primaire_pts_pib": "Solde primaire des APU (en pts de PIB)",
}

#: Each variant is addressed by the *shock sentence* the document prints above its
#: table, not by its section number: the section heading sometimes resolves to the
#: block title ("4.1. Chocs budgétaires et fiscaux") rather than to the variant, and a
#: silently mismatched table is the failure this project keeps meeting.
#:
#: `expansionary_sign` converts each published table to one convention — **GDP response
#: per point of GDP of expansionary impulse**. Mésange publishes some variants as a
#: cut and others as a rise; without this, a VAT rise and an income-tax cut would sit
#: in the same column with opposite meanings. It is a sign flip on a linear model, and
#: it inherits that model's symmetry assumption: the document does not measure whether
#: a tax rise costs what an equal tax cut buys.
VARIANTS: dict[str, tuple[str, int]] = {
    "investissement_public": ("Hausse de l’investissement public de 1 % du PIB en volume", +1),
    "depense_publique": ("Hausse de la dépense publique d’un montant de 1 point de PIB", +1),
    "cotisations_employeurs": (
        "Baisse des cotisations sociales employeurs de 1 % du PIB ex ante", +1),
    "cotisations_salaries": (
        "Baisse des cotisations sociales salariés de 1 % du PIB ex ante", +1),
    "tva": ("Hausse de la TVA de 1 % du PIB ex ante", -1),
    "csg": ("Baisse de la contribution sociale généralisée de 1 % du PIB ex ante", +1),
    "impot_sur_le_revenu": (
        "Baisse de l’impôt sur le revenu des ménages de 1 % du PIB ex ante", +1),
    "taxe_carbone": ("Hausse de la taxe carbone de 1 pt de PIB", -1),
}

#: Instruments the reform engine can move, mapped to the variant that represents them.
#: An instrument absent here has no multiplier and must not silently borrow one.
INSTRUMENT_VARIANTS = {
    "ir": "impot_sur_le_revenu",
    "csg": "csg",
    "cotisations_salariales": "cotisations_salaries",
    "cotisations_employeurs": "cotisations_employeurs",
    "tva": "tva",
}


class MesangeError(RuntimeError):
    """The Mésange document cannot be read as expected."""


@dataclass(frozen=True)
class Variant:
    """One published variant, in the expansionary convention."""

    key: str
    shock: str
    """The document's own sentence describing the shock, verbatim."""
    rows: dict[str, tuple[float, ...]]
    page: int
    published_sign: int
    """+1 if the document published this as an expansionary shock, -1 if it published a
    contractionary one and the rows have been flipped to match the others."""

    def at(self, row: str, horizon: str) -> float:
        if row not in self.rows:
            raise MesangeError(f"variant {self.key!r} has no row {row!r}")
        if horizon not in HORIZONS:
            raise MesangeError(f"unknown horizon {horizon!r}; have {HORIZONS}")
        return self.rows[row][HORIZONS.index(horizon)]

    @property
    def multiplier(self) -> tuple[float, ...]:
        """GDP response per point of GDP of expansionary impulse, by horizon."""
        return self.rows["gdp"]

    @property
    def jobs(self) -> tuple[float, ...]:
        """Thousands of market-sector employees, by horizon."""
        return self.rows["emploi_milliers"]


def _normalise(text: str) -> str:
    """Collapse whitespace and settle the apostrophe.

    The document uses U+2019 throughout; extractors and editors do not always agree,
    and a shock sentence that fails to match by one apostrophe would raise as a missing
    variant rather than as the encoding problem it is.
    """
    return " ".join(text.replace("\u0027", "\u2019").split())


def _numbers(line: str, label: str) -> tuple[float, ...]:
    tail = line[len(label):]
    # French decimals, and a minus sign that the extractor renders as a hyphen.
    found = re.findall(r"-?\d+(?:[,.]\d+)?", tail)
    values = tuple(float(v.replace(",", ".")) for v in found)
    if len(values) != len(HORIZONS):
        raise MesangeError(
            f"row {label!r} yielded {len(values)} numbers, expected {len(HORIZONS)}: "
            f"{values}"
        )
    return values


def load(raw: Path | None = None) -> dict[str, Variant]:
    """Every budgetary variant, parsed from the published document.

    Raises on any variant it cannot find. A missing multiplier must kill its feature
    rather than fall back to a neighbour's number.
    """
    path = (raw or RAW) / SOURCE_FILE
    if not path.exists():
        raise MesangeError(f"{path} not found — download it and record it in the manifest")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise MesangeError("pypdf is required to read the Mésange document")

    pages = _pages(str(path))

    variants: dict[str, Variant] = {}
    for key, (shock, sign) in VARIANTS.items():
        target = _normalise(shock)
        for number, lines in pages:
            if not any(line.startswith(target) for line in lines):
                continue
            rows = {}
            for name, label in ROWS.items():
                line = next((line for line in lines if line.startswith(label)), None)
                if line is None:
                    break
                # The whole table flips together, the primary balance included: the
                # convention reverses the SHOCK, not a selection of its consequences.
                # A VAT rise improving the balance by 0.80 becomes a VAT cut costing
                # 0.80, and the row keeps corresponding to the same simulated measure.
                # Legitimate only because the model is linear, which is why the
                # symmetry assumption is stated on every row that carries it.
                values = _numbers(line, label)
                rows[name] = values if sign > 0 else tuple(-v for v in values)
            if len(rows) != len(ROWS):
                continue
            variants[key] = Variant(key=key, shock=shock, rows=rows, page=number,
                                    published_sign=sign)
            break
        else:
            raise MesangeError(
                f"variant {key!r} not found: no page carries the shock sentence "
                f"{shock!r}. The document may have been revised — do not guess a value."
            )
    return variants


@lru_cache(maxsize=4)
def _pages(path: str) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Extracted lines per page, cached: 150 pages of PDF is seconds, and the tests
    read the same document a dozen times. Returns tuples so the cache cannot be
    mutated by a caller."""
    import pypdf

    return tuple(
        (i + 1, tuple(_normalise(line) for line in (page.extract_text() or "").splitlines()))
        for i, page in enumerate(pypdf.PdfReader(path).pages)
    )
