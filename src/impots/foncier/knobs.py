"""F5 M2 — the taxe foncière knobs, and what each one is a claim about.

Three levers, and they are not the same kind of thing. Saying which is which is most of
the honesty available here, because a TF reform expressed at the wrong level answers a
different question than the one asked.

* **The revalorisation coefficient** — the annual uplift applied to every valeur locative
  nationally. The fiscally hottest TF parameter and the one nobody votes on separately:
  since 2018 it follows the IPCH of the previous November by law, so «changing» it is a
  change to an indexation RULE and not to a rate. It moves every commune at once and it
  moves the BASE, which is why a one-point change is worth more than a one-point rate
  change.
* **A national rate change** — every commune's rate moved by the same amount. Expressible,
  and almost always a fiction: rates are voted commune by commune, and no national actor
  can set them. It prices «what if every council did X», which is a legitimate question
  and not a policy.
* **A rate change on a set of communes** — the honest shape of most real TF questions,
  because it is the level at which the decision actually sits.

WHAT IS OUT OF SCOPE IN V1, per the phase spec and repeated here because a reader will
wonder: the 2028 **révision des valeurs locatives** is a structural change to how bases are
computed, not a parameter, and it gets its own gate if it survives. Nor does this module
read the fine structure of exonérations — which is part of why 55 communes do not reconcile
(D-111), and pretending otherwise would be inventing the very structure that is missing.

EVERY KNOB IS A MULTIPLIER OR AN ADDITION ON PUBLISHED CELLS. Nothing is fitted, nothing is
drawn, and the baseline the reform is compared against is the REI's own produits — so a TF
chiffrage is our arithmetic against their arithmetic on their data, which is the strongest
comparison this project makes anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from impots.foncier.cells import Cells, produit_of

#: The revalorisation coefficient's legal basis, stated because the knob is a change to a
#: RULE and a reader must know which rule. CGI art. 1518 bis: since the LF 2017 the annual
#: coefficient equals one plus the year-on-year IPCH of November N-1, so it is not voted
#: each year — it is read off an index.
REVALORISATION_REFERENCE = (
    "CGI art. 1518 bis — depuis la LF 2017, le coefficient annuel de revalorisation "
    "forfaitaire des valeurs locatives vaut 1 + la variation de l'IPCH de novembre N-1. "
    "Il n'est donc pas voté chaque année : il se lit sur un indice. Le modifier est un "
    "changement de RÈGLE d'indexation, pas de taux."
)


class KnobError(RuntimeError):
    """A taxe foncière reform was asked for in a way that would mislead."""


@dataclass(frozen=True)
class FoncierReform:
    """A TF reform, expressed on published cells.

    `revalorisation` multiplies every base; `taux_delta_points` adds to every rate in
    PERCENTAGE POINTS (0.5 means «one commune's 19,40 % becomes 19,90 %», not «+0,5 %»);
    `communes` restricts a rate change to a set of INSEE department+commune codes.
    """

    revalorisation: float | None = None
    taux_delta_points: float | None = None
    communes: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.revalorisation is None and self.taux_delta_points is None:
            raise KnobError(
                "une réforme foncière vide : donner un coefficient de revalorisation, "
                "un déplacement de taux, ou les deux.")
        if self.revalorisation is not None and not 0.5 < self.revalorisation < 2.0:
            raise KnobError(
                f"coefficient de revalorisation {self.revalorisation} hors de ]0,5 ; 2[ : "
                f"c'est un MULTIPLICATEUR de base (1,032 pour +3,2 %), pas un taux.")
        if self.taux_delta_points is not None and abs(self.taux_delta_points) > 50:
            raise KnobError(
                f"déplacement de taux de {self.taux_delta_points} points : les taux "
                f"communaux de TFPB tournent autour de 20-40 %, donc c'est "
                f"vraisemblablement une fraction passée pour des points.")
        if self.communes is not None:
            if self.taux_delta_points is None:
                raise KnobError(
                    "restreindre à un ensemble de communes n'a de sens que pour un "
                    "changement de TAUX : la revalorisation est nationale par "
                    "construction (elle porte sur les valeurs locatives, pas sur une "
                    "décision locale).")
            if not self.communes:
                raise KnobError("ensemble de communes vide")


def price(cells: Cells, reform: FoncierReform,
          stratum: str = "commune") -> dict[str, float]:
    """Price a TF reform on published cells. Returns baseline, reform and delta, in EUR.

    The baseline is `produit_of` — our arithmetic on their bases — and NOT the REI's
    published produit column. That is deliberate and it matters: comparing a reformed
    figure computed one way against a baseline read another way would fold the identity's
    own residual into every reform's cost. The residual is small (median 0,006 %) but it
    is not zero, and it has no business inside a chiffrage.
    """
    import polars as pl

    if stratum not in cells.strata:
        raise KnobError(f"strate « {stratum} » absente : {list(cells.strata)}")
    base_col, rate_col = f"fb_{stratum}_base", f"fb_{stratum}_taux"

    base = pl.col(base_col)
    rate = pl.col(rate_col)
    if reform.revalorisation is not None:
        base = base * reform.revalorisation
    if reform.taux_delta_points is not None:
        if reform.communes is None:
            rate = rate + reform.taux_delta_points
        else:
            code = pl.col("dep") + pl.col("com")
            rate = pl.when(code.is_in(list(reform.communes))) \
                     .then(rate + reform.taux_delta_points).otherwise(rate)

    lissage = f"fb_{stratum}_lissage"
    reformed = base * rate / 100.0
    if lissage in cells.frame.columns:
        reformed = reformed + pl.col(lissage)

    baseline = float(cells.frame.select(produit_of(cells, stratum).sum()).item())
    after = float(cells.frame.select(reformed.sum()).item())
    return {"baseline_eur": baseline, "reform_eur": after,
            "delta_eur": after - baseline}


def touched_communes(cells: Cells, reform: FoncierReform) -> int:
    """How many communes a reform actually moves.

    Reported because a rate change restricted to a commune set that matches nothing
    prices at exactly zero, and a zero that means «no commune matched» is
    indistinguishable from a zero that means «the measure is free» unless somebody counts.
    """
    import polars as pl

    if reform.communes is None:
        return int(cells.frame.height)
    code = pl.col("dep") + pl.col("com")
    return int(cells.frame.filter(code.is_in(list(reform.communes))).height)


def price_checked(cells: Cells, reform: FoncierReform,
                  stratum: str = "commune") -> dict[str, Any]:
    """`price`, with the empty-set refusal that a bare zero would hide."""
    touched = touched_communes(cells, reform)
    if reform.communes is not None and touched == 0:
        raise KnobError(
            f"aucune des {len(reform.communes)} communes demandées n'existe dans le "
            f"REI {cells.vintage}. Le chiffrage vaudrait exactement zéro, et ce zéro se "
            f"lirait « la mesure est gratuite » au lieu de « la mesure ne porte sur "
            f"personne ». Vérifier les codes INSEE (département sur 2 ou 3 caractères "
            f"puis commune sur 3).")
    out = dict(price(cells, reform, stratum))
    out["communes_touchees"] = float(touched)
    return out
