"""Phase 9 M1 — the growth and rate scenarios a debt path may not be drawn without.

`path.project` already refuses a path with no named SPENDING scenario. A path also rests
on a growth hypothesis and a rate hypothesis, and until now both arrived as bare floats in
`YearInputs`: numbers nobody named, which the chart could not display and the reader could
not question. They become objects here, under the same name guard as spending
(`path.check_scenario_name`), so the three names a chart shows obey one rule.

WHAT THESE ARE NOT. A growth scenario is not a forecast of growth and a rate scenario is
not a forecast of rates. The project does not predict either; the caller states them, the
chart names them, and changing them changes the answer — which is the point of naming
them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from impots.dette.path import DebtError, check_scenario_name


@dataclass(frozen=True)
class GrowthScenario:
    """Nominal GDP growth, in its two parts.

    The split is not decoration: `gele_en_volume` grows spending with PRICES only, so a
    spending ratio cannot be computed from nominal growth alone. A scenario that gave one
    rate would force the code to guess how much of it is inflation.
    """

    name: str
    real: float
    """Annual growth of GDP in volume."""
    prices: float
    """Annual growth of the GDP deflator."""

    def __post_init__(self) -> None:
        check_scenario_name(self.name, "de croissance")
        for label, rate in (("réelle", self.real), ("des prix", self.prices)):
            if rate <= -1.0:
                raise DebtError(
                    f"croissance {label} de {rate} : à −100 % ou moins le niveau s'annule "
                    f"ou change de signe, et aucun ratio au PIB n'a plus de sens.")

    @property
    def nominal(self) -> float:
        return (1.0 + self.real) * (1.0 + self.prices) - 1.0


RateKind = Literal["implicite_tenu", "marche"]


@dataclass(frozen=True)
class RateScenario:
    """How the debt is charged.

    * ``implicite_tenu`` — the implicit rate stays at its last realized value, and new
      debt is charged at that same rate. The simplest hypothesis, and named as one.
    * ``marche`` — maturing State securities roll over at ``market_rate``
      (`maturite.implicit_rate_path`, on the AFT outstanding), and every euro of extra
      debt a reform adds is charged at ``market_rate``. It needs the manifested AFT
      files, and refuses without them.
    """

    name: str
    kind: RateKind
    market_rate: float | None = None

    def __post_init__(self) -> None:
        check_scenario_name(self.name, "de taux")
        if self.kind not in ("implicite_tenu", "marche"):
            raise DebtError(f"scénario de taux « {self.kind} » inconnu")
        if self.kind == "marche" and self.market_rate is None:
            raise DebtError(
                "« marché » sans taux de marché : le taux EST le scénario, et le défaut "
                "silencieux serait le scénario que personne n'a choisi.")
        if self.kind == "implicite_tenu" and self.market_rate is not None:
            raise DebtError(
                "un taux de marché a été fourni avec « implicite_tenu », qui n'en lit "
                "aucun : il serait ignoré en silence et le graphique afficherait un nom "
                "qui ne décrit pas le calcul.")
