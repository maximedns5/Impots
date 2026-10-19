"""Reading the IPP's report n° 22 on the 2008 CIR reform (Phase 9 M5, D-222).

Bozio, Cottet and Py estimate how much the R&D of firms already using the CIR rose after
the 2008 reform, per euro of créance. Their tables print a multiplier per specification
(1,31 to 1,52 in the preferred approach); their conclusion narrows it to the range they
find most credible, « légèrement supérieures à 1, entre 0.8 et 1.4 dans les intervalles
de confiance les plus crédibles » (p. 77). The store row is that range: this module reads
it out of the PDF so the row is checked against the file rather than a retyping (D-026).
"""

from __future__ import annotations

import importlib.util
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
SOURCE_FILE = "ipp_rapport_22_2019_bozio_cottet_py_cir.pdf"

CONCLUSION = re.compile(
    r"multiplicateur du crédit d.impôt recherche légèrement supérieures à 1, entre "
    r"(\d[.,]\d) et (\d[.,]\d) dans les intervalles de confiance les plus crédibles")


class Ipp22Error(RuntimeError):
    """The report cannot be read as expected."""


@dataclass(frozen=True)
class Range:
    low: float
    central: float
    high: float


def credible_range(raw: Path | None = None) -> tuple[float, float]:
    """(low, high) of the authors' « most credible » multiplier, from their conclusion."""
    path = (raw or RAW) / SOURCE_FILE
    if not path.exists():
        raise Ipp22Error(f"{path} introuvable — téléchargez-le par le manifeste "
                         f"(`impots data fetch {SOURCE_FILE}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise Ipp22Error("pypdf est requis pour lire le rapport")
    import pypdf

    for page in reversed(pypdf.PdfReader(str(path)).pages):
        # NFKC: the PDF sets « confiance » with the fi ligature, which no pattern matches.
        text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", page.extract_text() or ""))
        match = CONCLUSION.search(text)
        if match:
            return tuple(float(g.replace(",", ".")) for g in match.groups())
    raise Ipp22Error("la phrase de conclusion sur le multiplicateur est introuvable")


def convention(low: float, high: float) -> Range:
    """The store row of D-222: the authors' credible range, centred on its middle — the
    « légèrement supérieures à 1 » of the same sentence."""
    return Range(low=low, central=round((low + high) / 2, 10), high=high)
