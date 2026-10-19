"""The CIR priced on the créance flow — Phase 8's gate on it, resolved (D-222).

PHASE8_SPEC §2.3.3 held the CIR in bucket C until « MESR GECIR publications support a
créance-based re-pricing with the créance/décaissement distinction explicit », and D-154
found no GECIR publication in the manifest. Two are there now. The 2019 semi-definitive
long publication prints what a re-pricing needs: research expenses and créance on each
side of the 100 M€ threshold (its tableau 04), the rates (« 30 % jusqu'à un seuil de
100 M€, et de 5 % au-delà »), and an inset that says in so many words that the créance of
a millésime is not the dépense fiscale of a year.

THE INSTRUMENT. Two components on a fixed base: 30 % on the research expenses each
declarant carries below 100 M€, 5 % on those above. Rebuilt from the table, they must land
on the published créance within the engine's tolerance, or the instrument refuses to
exist. A rate change re-prices the créance of the millésime, base held fixed.

THE BANNER, AND WHY IT IS NOT A FOOTNOTE. A créance is consumed over five or six calendar
years — imputed on the IS for three, then refunded — so the budget's dépense fiscale for
a year mixes several millésimes. The Voies et Moyens figure is read beside the créance and
never in its place. And the stock of créances carried forward is not measured here: the
same class as Phase 7's L4, which the spec allows to be priced « with a banner ».
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from impots.agregats.engine import (
    AggregateError,
    AggregateInstrument,
    MechanicalResult,
    RateComponent,
    ReceiptsAnchor,
)

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
GECIR_FILE = "mesr_gecir_cir_2019_semi_definitif_publication_longue.pdf"
VM_FILE = "plf2026_voies_et_moyens_tome2.pdf"

CODE = "cir"
LABEL = "Crédit d'impôt recherche (créance du dispositif recherche)"
LOW, HIGH = "cir_recherche_30", "cir_recherche_5"

#: The knobs, and the component each one sets.
KNOBS = {"cir_taux": LOW, "cir_taux_au_dela": HIGH}

BANNER = (
    "CRÉANCE, PAS DÉCAISSEMENT. Le chiffre est la variation de la créance du millésime "
    "{millesime} (données GECIR semi-définitives), à dépenses de recherche inchangées. "
    "L'État ne la paie pas dans l'année : une créance s'impute sur l'IS pendant trois "
    "ans puis se restitue, et la dépense fiscale d'une année consomme les créances de "
    "cinq ou six millésimes. Le stock de créances reportées n'est pas mesuré.")

#: Pieces of the text read out of the publication, each with the figures it carries.
NUM = r"\d{1,3}(?: \d{3})*"
PCT = r"\d+,\d"
TABLE_TITLE = re.compile(r"Tableau 04 \S*\s*Répartition des déclarants au CIR\S*recherche "
                         r"(\d{4}), selon le seuil des 100 M€")
ROW = rf"\s+({NUM})\s+({NUM})\s+({PCT}) %\s+({NUM})\s+({PCT}) %\s+({PCT}) %"
ROWS = {
    "below": re.compile(r"dont parts inférieures à 100 M€" + ROW),
    "above": re.compile(r"dont parts supérieures à 100 M€" + ROW),
    "others": re.compile(r"Autres déclarants" + ROW),
    "total": re.compile(r"TOTAL" + ROW),
}
RATES = re.compile(r"(\d+) % jusqu.à un seuil de (\d+) M€, et de (\d+) % au-delà")
#: Voies et Moyens tome II, the CIR's own sheet: three years, then three amounts.
AMOUNT = r"(\d{1,2} \d{3})"
#: The sheet prints « Modification 2025 » just before its three years, so the years are
#: the ones standing right before « Fin du fait générateur », and the amounts right after
#: its date — read anywhere else, the modification year passes for the first column.
DEPENSE_FISCALE = re.compile(
    r"200302 – Crédit d'impôt en faveur de la recherche.*?Réalisation Prévision Prévision"
    r".*?(\d{4}) (\d{4}) (\d{4}) Fin du fait générateur [^\d]*" + " ".join([AMOUNT] * 3))

#: The printed figures are rounded to the million: three of them summed may miss the
#: printed total by that much each.
ROUNDING_EUR = 3e6


@dataclass(frozen=True)
class GecirReading:
    millesime: int
    rate_low: float
    rate_high: float
    threshold_eur: float
    base_low_others_eur: float
    """The whole research expenses of the declarants that stay below the threshold."""
    base_low_big_eur: float
    """The parts below the threshold of the declarants that cross it: inframarginal, their
    next euro of research is credited at the reduced rate."""
    base_high_eur: float
    creance_eur: float
    """The published créance of the research scheme, all declarants."""
    page: int

    @property
    def base_low_eur(self) -> float:
        return self.base_low_others_eur + self.base_low_big_eur


class CirError(AggregateError):
    """A CIR source cannot be read as expected."""


def _eur(token: str) -> float:
    return float(token.replace(" ", "")) * 1e6


@lru_cache(maxsize=4)
def _pages(path: str) -> tuple[str, ...]:
    import pypdf

    return tuple(re.sub(r"\s+", " ", (page.extract_text() or "").replace("\xa0", " "))
                 for page in pypdf.PdfReader(path).pages)


def _path(raw: Path | None, name: str) -> str:
    path = (raw or RAW) / name
    if not path.exists():
        raise CirError(f"{path} introuvable — téléchargez-le par le manifeste "
                       f"(`impots data fetch {name}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise CirError("pypdf est requis pour lire les publications")
    return str(path)


def read_gecir(raw: Path | None = None) -> GecirReading:
    """Tableau 04 and the rates, out of the 2019 long publication."""
    pages = _pages(_path(raw, GECIR_FILE))
    page = next((k for k, text in enumerate(pages) if TABLE_TITLE.search(text)), None)
    if page is None:
        raise CirError("tableau 04 (le seuil des 100 M€) introuvable — le document a changé ?")
    text = pages[page]
    rows = {}
    for name, pattern in ROWS.items():
        match = pattern.search(text)
        if match is None:
            raise CirError(f"ligne « {name} » du tableau 04 illisible")
        rows[name] = (_eur(match.group(2)), _eur(match.group(4)))
    rates = next((m for t in pages if (m := RATES.search(t))), None)
    if rates is None:
        raise CirError("les taux du CIR-recherche sont introuvables dans le texte")
    reading = GecirReading(
        millesime=int(TABLE_TITLE.search(text).group(1)),
        rate_low=int(rates.group(1)) / 100.0, rate_high=int(rates.group(3)) / 100.0,
        threshold_eur=int(rates.group(2)) * 1e6,
        base_low_others_eur=rows["others"][0], base_low_big_eur=rows["below"][0],
        base_high_eur=rows["above"][0], creance_eur=rows["total"][1], page=page + 1)
    expenses = reading.base_low_eur + reading.base_high_eur
    if abs(expenses - rows["total"][0]) > ROUNDING_EUR:
        raise CirError(f"les dépenses de part et d'autre du seuil font {expenses / 1e6:.0f} M€ "
                       f"et le total imprimé {rows['total'][0] / 1e6:.0f} M€")
    return reading


def read_depense_fiscale(raw: Path | None = None) -> dict[int, float]:
    """{year: EUR} — the CIR's dépense fiscale (n° 200302), as Voies et Moyens prints it.
    The budget's figure for a year, beside the créance and never in its place."""
    pages = _pages(_path(raw, VM_FILE))
    match = next((m for t in pages if (m := DEPENSE_FISCALE.search(t))), None)
    if match is None:
        raise CirError("la fiche 200302 du tome II est introuvable")
    years = [int(match.group(k)) for k in (1, 2, 3)]
    if years != list(range(years[0], years[0] + 3)):
        raise CirError(f"la fiche 200302 donne les années {years}, pas trois années de suite")
    return {year: _eur(match.group(k + 4)) for k, year in enumerate(years)}


def instrument(reading: GecirReading) -> AggregateInstrument:
    """The two-rate instrument on the millésime's base; refuses to exist if the base split
    does not rebuild the published créance."""
    anchor = ReceiptsAnchor(
        instrument=CODE, year=reading.millesime, amount_eur=reading.creance_eur,
        manifest_file=GECIR_FILE,
        note=f"créance du dispositif recherche, millésime {reading.millesime} "
             f"(semi-définitif) — pas la dépense fiscale d'une année")
    built = AggregateInstrument(
        code=CODE, label=LABEL, anchor=anchor,
        components=(
            RateComponent(code=LOW, label=f"part des dépenses ≤ "
                          f"{reading.threshold_eur / 1e6:.0f} M€ par déclarant",
                          rate=reading.rate_low, base_eur=reading.base_low_eur),
            RateComponent(code=HIGH, label=f"part des dépenses > "
                          f"{reading.threshold_eur / 1e6:.0f} M€ par déclarant",
                          rate=reading.rate_high, base_eur=reading.base_high_eur),
        ),
        elasticity_reason=(
            "la réponse de la R&D est un canal du comportement (C9, D-222), pas une bande "
            "de recettes de l'instrument"),
    )
    built.check_base_split()
    return built


def price(reading: GecirReading, *, cir_taux: float | None = None,
          cir_taux_au_dela: float | None = None) -> MechanicalResult:
    """The créance of the millésime under new rates, research expenses held fixed."""
    rates = {component: value for component, value in
             ((LOW, cir_taux), (HIGH, cir_taux_au_dela)) if value is not None}
    return instrument(reading).reprice(rates)


def margins(reading: GecirReading, *, cir_taux: float | None = None,
            cir_taux_au_dela: float | None = None) -> tuple[tuple[float, float], ...]:
    """((Δ créance, marginal rate), ...) for the two groups of declarants, at fixed
    research expenses — what the R&D channel C9 reads (D-222).

    The declarants below the threshold get the rate change on their whole expenses and
    credit their next euro at the new full rate. Those that cross it get it on their part
    below, plus the reduced-rate change on their part above, and credit their next euro
    at the new reduced rate.
    """
    low = reading.rate_low if cir_taux is None else cir_taux
    high = reading.rate_high if cir_taux_au_dela is None else cir_taux_au_dela
    others = (low - reading.rate_low) * reading.base_low_others_eur
    big = ((low - reading.rate_low) * reading.base_low_big_eur
           + (high - reading.rate_high) * reading.base_high_eur)
    return ((others, low), (big, high))
