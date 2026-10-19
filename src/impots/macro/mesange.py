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

#: Row labels the ordinary variant tables print. The targeted variant overrides them:
#: it prints "PIB (en volume et en %)" and carries no price or balance rows at all.
ROWS_TARGETED = {
    "gdp": "PIB (en volume et en %)",
    "emploi_milliers": "Emploi salarié marchand (en milliers)",
    "emploi_qualifie": "Emploi qualifié",
    "emploi_non_qualifie": "Emploi non qualifié",
}


@dataclass(frozen=True)
class VariantSpec:
    """How to find one variant, and what the document says its shock actually is.

    Each field here exists because the adversarial pass found the row claiming
    otherwise. They are not decoration: `ex_ante_points` and `basis` change the
    arithmetic, and `targeted` decides which reforms may use the row at all.
    """

    shock: str
    """The sentence printed above the table, verbatim. Variants are addressed by it
    rather than by section number, since the heading sometimes resolves to the block
    title. NOT unique in the document — "Hausse de l'investissement public de 1 % du
    PIB en volume" also appears on p52 and p136 — so the reader additionally requires
    every expected row on the same page and keeps the first qualifying page."""

    expansionary_sign: int
    """+1 if published as an expansionary shock, -1 if published contractionary and
    flipped. The flip assumes symmetry. The document proves ADDITIVITY between
    instruments (encadré 15, the "TVA sociale" composite reproduces the sum of the VAT
    and employer-contribution variants to the centime) but never tests running one
    variant in both directions, so symmetry remains an unmeasured assumption."""

    basis: str
    """"ex_ante_fiscal" or "volume". p101 reserves the ex ante convention: "les
    variantes FISCALES sont effectuées à hauteur de 1 % du PIB ex ante, soit un montant
    de 22 Md€ en 2015". The two spending variants are shocks in VOLUME, so calling them
    ex ante — as this file did until the verification — mis-states three lines of eight."""

    ex_ante_points: float = 1.0
    """Points of GDP the shock actually costs ex ante. 1.0 everywhere except VAT, where
    p113 prints: "Considérant que les APU versent environ 15 % du total des recettes de
    TVA, le choc s'élève à 1,18 point de PIB ex ante pour atteindre effectivement 1
    point de PIB de recettes de TVA supplémentaires en termes nets." A VAT reform costed
    GROSS ex ante — the usual PLF convention — would otherwise receive a multiplier
    overstated by 18 %."""

    targeted: bool = False
    """True only for the low-wage variant of encadré 14. The eight main variants are
    UNIFORM: p118 "il n'existe dans le modèle qu'un unique taux d'imposition sur le
    revenu identique pour l'ensemble des salariés"; p108 a "baisse uniforme de 3,7
    points". Routing a low-wage allègement to a uniform variant understates employment
    by 39 % at three years."""

    rows: dict[str, str] | None = None
    caveat: str = ""


#: The published variants. `expansionary_sign` brings them all to one convention: GDP
#: response per point of GDP of expansionary impulse.
VARIANTS: dict[str, VariantSpec] = {
    "investissement_public": VariantSpec(
        "Hausse de l’investissement public de 1 % du PIB en volume", +1, "volume",
        caveat="Réparti au prorata de la composition moyenne de l'investissement public "
               "(61 % services abrités, 27 % services exposés, 11 % biens manufacturés), "
               "dont dépend le contenu en imports."),
    "depense_publique": VariantSpec(
        "Hausse de la dépense publique d’un montant de 1 point de PIB", +1, "volume",
        caveat="COMPOSITE, et non un instrument : 8 % investissement public, 25 % "
               "rémunérations publiques, 9 % prestations en nature, 12 % consommations "
               "intermédiaires, 46 % PRESTATIONS SOCIALES EN ESPÈCES (p106). Contient "
               "donc 8 % de la variante investissement public — les additionner double "
               "compte. Son emploi LT (-42 000 marchand) s'accompagne d'une HAUSSE de "
               "l'emploi total de 26 000 y compris public (p107) : rapporter le premier "
               "seul inverse la conclusion."),
    "cotisations_employeurs": VariantSpec(
        "Baisse des cotisations sociales employeurs de 1 % du PIB ex ante", +1,
        "ex_ante_fiscal",
        caveat="Baisse UNIFORME de 3,7 points, portant à 80 % sur des salariés qualifiés. "
               "Pour un allègement ciblé bas salaires, utiliser "
               "`cotisations_employeurs_ciblees`."),
    "cotisations_salaries": VariantSpec(
        "Baisse des cotisations sociales salariés de 1 % du PIB ex ante", +1,
        "ex_ante_fiscal",
        caveat="Baisse uniforme de 3,7 points sur un taux d'un peu plus de 13 %."),
    "tva": VariantSpec(
        "Hausse de la TVA de 1 % du PIB ex ante", -1, "ex_ante_fiscal",
        ex_ante_points=1.18,
        caveat="Le choc est de 1,18 point de PIB ex ante pour 1 point net, les APU "
               "versant ~15 % de la TVA."),
    "csg": VariantSpec(
        "Baisse de la contribution sociale généralisée de 1 % du PIB ex ante", +1,
        "ex_ante_fiscal"),
    "impot_sur_le_revenu": VariantSpec(
        "Baisse de l’impôt sur le revenu des ménages de 1 % du PIB ex ante", +1,
        "ex_ante_fiscal",
        caveat="Baisse uniforme d'environ 2,5 points du taux apparent : le modèle n'a "
               "qu'un seul taux d'imposition sur le revenu pour tous les salariés, donc "
               "il ne représente AUCUN effet de barème ni de progressivité."),
    "taxe_carbone": VariantSpec(
        "Hausse de la taxe carbone de 1 pt de PIB", -1, "ex_ante_fiscal",
        caveat="Le choc porte sur les VOLUMES d'énergie, et p121 avertit qu'il est "
               "difficile de transposer des points de PIB en euros par tonne de CO2 : "
               "« le calibrage d'une taxe carbone doit donc être réalisé hors modèle »."),
    "cotisations_employeurs_ciblees": VariantSpec(
        "Impact d’une baisse uniforme des cotisations sociales employeurs de 1 % du PIB "
        "ex ante, ciblée sur les salaires situés entre 1 et 1,6 Smic", +1,
        "ex_ante_fiscal", targeted=True, rows=ROWS_TARGETED,
        caveat="Encadré 14, présenté « à visée illustrative uniquement », et la note 79 "
               "précise que « son impact ne permet pas d'évaluer l'effet de mesures "
               "d'allègement de cotisations spécifiquement mises en place au cours des "
               "dernières années ». À utiliser malgré tout pour un allègement bas "
               "salaires : la variante uniforme donne 290 000 emplois à trois ans contre "
               "403 000 ici, soit une sous-estimation de 39 %."),
}

#: Simulation conditions every variant inherits (p101), and which no row stated until
#: the adversarial pass: "Sauf mention contraire, le choc est effectué de façon
#: permanente, à taux d'intérêt réels constants et à taux de change nominaux constants.
#: Il n'y a pas non plus de réaction endogène de la politique budgétaire."
SIMULATION_CONDITIONS = (
    "Choc permanent, à taux d'intérêt réels constants, à taux de change nominaux "
    "constants, sans réaction endogène de la politique budgétaire ni de la politique "
    "monétaire."
)

#: The "1 an" column is an AVERAGE over the first year, not an end-of-year level — the
#: shock lands in 2015Q1 and table 12 (p120) footnotes "il s'agit d'un effet moyen sur
#: la 1re année". A dated profile reading it as the level at t+4 quarters reads it wrong.
FIRST_YEAR_IS_AN_AVERAGE = True

#: Variants that overlap and must never be summed: `depense_publique` already contains
#: 8 % public investment.
NON_ORTHOGONAL = {("investissement_public", "depense_publique")}

#: Instruments the reform engine can move, mapped to the variant that represents them.
#: An instrument absent here has no multiplier and must not silently borrow one.
INSTRUMENT_VARIANTS = {
    "ir": "impot_sur_le_revenu",
    "csg": "csg",
    "cotisations_salariales": "cotisations_salaries",
    "cotisations_employeurs": "cotisations_employeurs",
    "cotisations_employeurs_bas_salaires": "cotisations_employeurs_ciblees",
    "tva": "tva",
}


class MesangeError(RuntimeError):
    """The Mésange document cannot be read as expected."""


@dataclass(frozen=True)
class Variant:
    """One published variant, in the expansionary convention."""

    key: str
    spec: VariantSpec
    rows: dict[str, tuple[float, ...]]
    page: int
    """1-based PDF page. The printed folio is this minus one — the public-investment
    table is folio 102 and PDF page 103 — so a citation must say which it means."""

    @property
    def shock(self) -> str:
        return self.spec.shock

    @property
    def published_sign(self) -> int:
        return self.spec.expansionary_sign

    @property
    def caveat(self) -> str:
        return self.spec.caveat

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
        raise MesangeError(f"{path} not found — download it and record it in the manifest "
                           f"(`impots data fetch {path.name}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise MesangeError("pypdf is required to read the Mésange document")

    pages = _pages(str(path))

    variants: dict[str, Variant] = {}
    for key, spec in VARIANTS.items():
        target = _normalise(spec.shock)
        sign = spec.expansionary_sign
        labels = spec.rows or ROWS
        for number, lines in pages:
            # Matched against the joined page rather than line by line: the targeted
            # variant's title wraps mid-sentence in the extraction. The safeguard
            # against the anchor appearing elsewhere (the public-investment sentence is
            # also on p52 and p136) stays what it was — every expected row must be on
            # the same page, and only the first qualifying page is kept.
            if target not in " ".join(lines):
                continue
            rows = {}
            for name, label in labels.items():
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
            if len(rows) != len(labels):
                continue
            variants[key] = Variant(key=key, spec=spec, rows=rows, page=number)
            break
        else:
            raise MesangeError(
                f"variant {key!r} not found: no page carries the shock sentence "
                f"{spec.shock!r} together with all of {sorted(labels)}. The document "
                f"may have been revised — do not guess a value."
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


def table(row: str, raw: Path | None = None, absent_for: tuple[str, ...] | list[str] = (),
          ) -> tuple[dict[str, tuple[float, ...]], tuple[str, ...]]:
    """One row of every variant, as (values by instrument, horizons).

    The adapter the parameter store addresses every reader through, so that adding a
    source does not mean adding a branch to the store.

    `absent_for` names the variants the YAML DECLARES do not print this row — the
    targeted variant has no balance row (D-214). Declared, not tolerated: a variant
    missing the row without being named is still refused, and a variant named that does
    print it is refused too, because the declaration would then be stale and the row
    silently narrower than the document.
    """
    variants = load(raw=raw)
    declared = set(absent_for)
    unknown = sorted(declared - set(variants))
    if unknown:
        raise MesangeError(f"absent_for names variants that do not exist: {unknown}")
    stale = sorted(k for k in declared if row in variants[k].rows)
    if stale:
        raise MesangeError(f"row {row!r} is declared absent for {stale}, which print it")
    missing = [key for key, variant in variants.items()
               if row not in variant.rows and key not in declared]
    if missing:
        raise MesangeError(f"row {row!r} absent from variants {missing}")
    return {key: variant.rows[row] for key, variant in variants.items()
            if key not in declared}, HORIZONS
