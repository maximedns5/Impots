"""ERFS — the disclosure guard, and why it is not a quoted threshold.

THE CONVENTION STATES NO NUMBER. It was found and read (Progedo-ADISP, demande n° 38715;
engagement de confidentialité auprès du Comité du Secret Statistique, signed 2025-09-03),
and what it requires is a **duty of result**, not a threshold:

    « de manière générale, toute procédure nécessaire dans le but d'empêcher
      l'identification directe ou indirecte d'unités statistiques individuelles »

It delegates numbers to « les règles générales du secret statistique » and to « les règles
de secret éventuellement spécifiques à certaines sources (disponibles dans leur
documentation ou auprès des producteurs) ». The ERFS documentation we hold — methodology,
FPR dictionary, EEC code dictionary — states none either: it describes diffusion TABLES,
not a cell rule.

**So there is nothing to quote, and pretending otherwise would be worse than admitting it.**
D-134 recorded 11 households as the handoff's fallback; that number is not in the convention
and never was. What replaces it is not a better number but a different mechanism:

* the floor is an EXPLICIT INPUT with no silent default — a caller must state it, so the
  number is always somebody's stated choice rather than a constant nobody re-examined;
* every aggregate is checked against the UNWEIGHTED cell count behind it, because weights
  inflate a cell of three households into thousands of people and a weighted count discloses
  exactly as much as the three;
* the check REFUSES rather than warns, and the refusal names the cell.

WHY A HIGH FLOOR COSTS NOTHING HERE, which is the argument that makes the missing number
unimportant. Everything E2 published clears any plausible rule by orders of magnitude: the
smallest cell in the A2 table holds 163 unweighted households. A floor of 11, 50 or even 100
changes nothing about what this project has published or plans to. The honest posture is
therefore to set the floor well above every candidate rule and let it bind on anything new —
a threshold that only ever refuses what nobody wanted to publish costs nothing and removes
the need to guess what the producer meant.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The reference, now known and no longer a blank. Recorded here because a compliance rule
#: whose source cannot be named is one nobody can check.
CONVENTION = "Progedo-ADISP, demande n° 38715 — engagement de confidentialité auprès du " \
             "Comité du Secret Statistique, signé le 2025-09-03"

#: Suggested floor. NOT from the convention — it states none — and deliberately well above
#: the fallback it replaces. Offered as a default argument nowhere: `check` requires it.
SUGGESTED_FLOOR = 50


class DisclosureRefused(RuntimeError):
    """An aggregate was about to be emitted from too few underlying units."""


@dataclass(frozen=True)
class Cell:
    """One published figure and the unweighted count standing behind it."""

    label: str
    unweighted_count: int


def check(cells: list[Cell], *, floor: int) -> None:
    """Refuse the whole table if any cell is thinner than `floor`.

    THE WHOLE TABLE, not the offending cell. Dropping one cell from a table whose margins
    are also published lets the dropped value be recovered by subtraction — suppression
    that can be undone by arithmetic is not suppression. Refusing everything forces the
    caller to re-aggregate rather than to patch.
    """
    if floor < 1:
        raise DisclosureRefused(
            f"plancher {floor} : un plancher inférieur à 1 n'interdit rien, et un garde "
            f"qui n'interdit rien se lit comme une garantie.")
    thin = [c for c in cells if c.unweighted_count < floor]
    if thin:
        raise DisclosureRefused(
            f"{len(thin)} case(s) sous le plancher de {floor} unités non pondérées : "
            f"{[c.label for c in thin][:5]}. La convention ({CONVENTION}) ne fixe aucun "
            f"seuil chiffré — elle impose « toute procédure nécessaire dans le but "
            f"d'empêcher l'identification directe ou indirecte d'unités statistiques "
            f"individuelles ». Le tableau ENTIER est refusé : retirer la seule case fine "
            f"d'un tableau dont les marges sont publiées la laisse retrouvable par "
            f"soustraction.")


def minimum(cells: list[Cell]) -> int:
    """The thinnest cell, for reporting alongside a table that passed."""
    if not cells:
        raise DisclosureRefused("aucune case : un tableau vide ne se vérifie pas")
    return min(c.unweighted_count for c in cells)
