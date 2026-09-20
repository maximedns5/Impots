"""Phase 8 §2.2 — the receipts anchors, as a FILE the owner fills, never a literal.

`ReceiptsAnchor` takes an `amount_eur`. Somebody has to put a number there, and the
whole point of that dataclass is that the number must be traceable to a manifested
file. A figure typed into a Python module is a recollection wearing a source's clothes:
the manifest entry beside it proves a document exists, not that the number came out of
it.

So the numbers live in `data/processed/receipts_anchors.json`, which is **generated on
a machine that has `data/raw/`** and is gitignored like every other processed table
(the firm cells work exactly this way). This module reads it, guards it, and refuses
loudly when it is absent — naming what to do rather than failing obscurely.

WHAT EACH GUARD IS FOR, AND WHAT WOULD MAKE IT FIRE.

* **The vintage convention is declared per row, and a row without one is refused.**
  Voies et Moyens columns are BUDGET years; the comptes nationaux are something else
  again; a model in 2024 incomes reads neither by default. Three times already the
  timing convention of the comparator WAS the entire error (D-026, D-067) — so the row
  states which calendar it is on, and a row that does not is not loaded.
* **Provenance is re-checked here, not assumed from the file's existence.**
  `ReceiptsAnchor.verify()` refuses a quarantined or URL-less entry. D-152 found the
  trap this closes: the natural Voies et Moyens copy IS quarantined while a
  byte-identical sourced twin sits beside it under another name, so «  absent  » and
  « not reproducible » look the same from a distance and are not the same thing.
* **Duplicate instrument codes are refused.** Two rows for one instrument means one
  silently wins, and which one depends on dict order — a number chosen by accident.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from impots.agregats.engine import AggregateError, ReceiptsAnchor

#: Generated, not committed — like `data/processed/firm_cells_*.json`.
ANCHOR_TABLE = Path("data/processed/receipts_anchors.json")

#: Which calendar a row's `year` is on. There is no default, and that is the guard:
#: every one of these has been the whole error at least once in this project.
VINTAGE_CONVENTIONS: tuple[str, ...] = (
    "budget",                 # Voies et Moyens / exécution budgétaire — année budgétaire
    "revenus",                # année des revenus, comme le modèle micro
    "comptabilite_nationale",  # comptes nationaux, base 2020
)


class AnchorTableMissing(AggregateError):
    """The anchor table has not been generated on this machine.

    Its own class because it is not a defect: it is the expected state of any checkout
    without `data/raw/`, and the UI should say so rather than render an instrument with
    no number behind it.
    """


@dataclass(frozen=True)
class AnchorRow:
    """One line of the table, before it becomes a `ReceiptsAnchor`."""

    instrument: str
    year: int
    amount_eur: float
    manifest_file: str
    vintage_convention: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.vintage_convention not in VINTAGE_CONVENTIONS:
            raise AggregateError(
                f"{self.instrument} : convention de millésime "
                f"« {self.vintage_convention} » inconnue ; attendu l'une de "
                f"{VINTAGE_CONVENTIONS}. Sans elle, l'année de la ligne ne dit pas de "
                f"quel calendrier elle parle — et c'est la convention du comparateur "
                f"qui a déjà été l'erreur entière trois fois.")

    def anchor(self) -> ReceiptsAnchor:
        return ReceiptsAnchor(
            instrument=self.instrument, year=self.year, amount_eur=self.amount_eur,
            manifest_file=self.manifest_file,
            note=f"[{self.vintage_convention}] {self.note}".strip())


def load_anchors(path: Path | None = None, *, verify: bool = True
                 ) -> dict[str, ReceiptsAnchor]:
    """Every anchor in the table, keyed by instrument code, provenance checked.

    `verify=False` exists for tests that want the parsing without a manifest lookup; it
    is not for production use, and nothing in `src/` passes it.
    """
    table = Path(path) if path is not None else ANCHOR_TABLE
    if not table.exists():
        raise AnchorTableMissing(
            f"{table} n'existe pas. Les ancres de recettes ne sont pas dans le code : "
            f"elles sont lues depuis cette table, qui se remplit sur une machine "
            f"disposant de data/raw/. Voir docs/M2_ANCHORS.md — quel document, quelle "
            f"colonne, et le contrôle à faire avant de s'en servir.")
    payload = json.loads(table.read_text(encoding="utf-8"))
    rows = payload["anchors"] if isinstance(payload, dict) else payload

    anchors: dict[str, ReceiptsAnchor] = {}
    for raw in rows:
        row = AnchorRow(**raw)
        if row.instrument in anchors:
            raise AggregateError(
                f"{row.instrument} : deux lignes pour un même instrument dans {table}. "
                f"L'une gagnerait selon l'ordre du fichier, donc le chiffre retenu "
                f"serait choisi par accident.")
        anchor = row.anchor()
        if verify:
            anchor.verify()
        anchors[row.instrument] = anchor
    return anchors
