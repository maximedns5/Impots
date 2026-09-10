"""F6 / Phase 6 S5 — the EMTR landscape, made explorable rather than summarised.

**No new model claims.** Every number here comes out of machinery that already exists and
is already tested: the engine, the finite-difference EMTR in `behavioural.emtr`, and the
population runner's full tier. What is new is only that the rates become *legible* across
an income range instead of arriving as one distribution statistic.

WHAT IT IS FOR. D-033 records the finding this module exists to make explorable: on the
2024 population, median EMTR runs from 20,8 % in the first decile of marginal rates to
**63,5 %** in the tenth — and **the households in that top decile are poor, not rich**.
That sentence is the whole argument, and a decile table is a poor way to see why. Sweeping
one household type across the income range shows the mechanism: the PPA and RSA tapers
stacking on each other, then unstacking, then the first IR bracket arriving on top.

HOW IT IS COMPUTED, AND WHY IT IS NOT A LOOP. A single household priced at full tier with
its EMTR costs about 2,5 s, so sixty points priced one at a time — twice, for baseline and
reform — is five minutes. But `behavioural.emtr.compute` already prices an entire FRAME in
one pass. So a sweep is a synthetic frame carrying one household per income point, and the
whole curve costs the same four full-tier runs a population EMTR costs. Reusing that path
also means the sweep inherits its guards rather than growing its own.

FULL TIER IS NOT NEGOTIABLE HERE, and D-033 says why: «the taper of PPA and RSA is a large
part of the marginal rate at low wages, and ignoring it would understate the real figure
badly». A light-tier sweep would draw a tidy curve that is simply wrong exactly where the
policy argument lives. `behavioural.emtr` enforces this itself; this module never asks for
anything else.

A RATE ABOVE 100 % IS A CLIFF, AND ITS HEIGHT IS AN ARTEFACT. The finite difference is
taken over 100 EUR, so a discontinuity that withdraws 47 EUR of benefit inside that window
reads as 147 % — and the same cliff measured over 500 EUR would read as 109 %. The
LOCATION of such a point is a finding; its HEIGHT is a property of the measurement step
and must never be quoted as a rate anybody faces. `Curve.cliffs` names them so a renderer
can mark them rather than plot them as if they were tapers.

THE HOUSEHOLDS ARE SYNTHETIC AND SAY SO. A sweep is not a sample of anybody: it is one
constructed household type walked across an income range, each point weighted 1. Reading a
distribution off it would be reading a distribution off a ruler. The artefact carries
`synthetic: true` on every row and the renderer prints the household type in full, because
an EMTR curve without its household type is a curve of nothing in particular — the rate at
24 000 EUR differs entirely between a single tenant and a couple with two children.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The income grid. 500 EUR steps read the tapers without pretending to more resolution
#: than the 100 EUR finite difference underneath can support.
DEFAULT_STEP_EUR = 500.0
DEFAULT_MAX_EUR = 60_000.0

#: The household types offered. Each is a complete specification, because an EMTR is a
#: property of a household and not of an income: at 24 000 EUR a single tenant and a
#: couple with two children are on entirely different parts of the landscape.
#:
#: Kept as data so the UI, the CLI and the tests all read the same list and a type added
#: here appears everywhere at once.
HOUSEHOLD_TYPES: dict[str, dict[str, Any]] = {
    "celibataire_locataire": {
        "label": "Célibataire, locataire (loyer 700 €/mois, zone 2)",
        "adults": 1, "children": 0, "loyer_mensuel": 700.0,
        "statut_occupation": "locataire_vide", "zone_apl": "zone_2",
    },
    "celibataire_proprietaire": {
        "label": "Célibataire, propriétaire",
        "adults": 1, "children": 0, "loyer_mensuel": 0.0,
        "statut_occupation": "proprietaire", "zone_apl": "zone_2",
    },
    "parent_isole_2_enfants": {
        "label": "Parent isolé, 2 enfants, locataire (loyer 800 €/mois, zone 2)",
        "adults": 1, "children": 2, "loyer_mensuel": 800.0,
        "statut_occupation": "locataire_vide", "zone_apl": "zone_2",
    },
    "couple_2_enfants": {
        "label": "Couple mono-actif, 2 enfants, locataire (loyer 900 €/mois, zone 2)",
        "adults": 2, "children": 2, "loyer_mensuel": 900.0,
        "statut_occupation": "locataire_vide", "zone_apl": "zone_2",
    },
}


class ExplorerError(RuntimeError):
    """A sweep was asked for in a way that would produce a misleading curve."""


@dataclass(frozen=True)
class CurvePoint:
    salaire_brut_annuel: float
    emtr: float
    emtr_reform: float | None = None


@dataclass(frozen=True)
class Curve:
    """One household type walked across an income range."""

    household_type: str
    label: str
    year: int
    points: tuple[CurvePoint, ...]
    reform: dict[str, Any] | None = None

    @property
    def peak(self) -> CurvePoint:
        """The highest rate on the curve, baseline. The thing a reader is looking for."""
        return max(self.points, key=lambda p: p.emtr)

    @property
    def cliffs(self) -> tuple[CurvePoint, ...]:
        """Points where the rate exceeds 100 % — a cliff, not a taper.

        AN EMTR ABOVE 100 % MEANS AN EXTRA EURO OF GROSS LEAVES THE HOUSEHOLD WORSE OFF.
        That is a real feature of the French landscape and the explorer's job is to show
        it. But **its exact value is an artefact of the finite-difference step**: the
        rate is measured over a 100 EUR bump, so a cliff that removes 47 EUR of benefit
        reads as 147 %, and the same cliff measured over 500 EUR would read as 109 %.

        So the height of a cliff point is not a rate anybody faces — it is a signal that
        a discontinuity sits inside that 100 EUR. The LOCATION is the finding; the
        height is a measurement artefact and the renderer says so rather than letting a
        reader quote «147 %».
        """
        return tuple(p for p in self.points if p.emtr > 1.0)

    def crossings(self, threshold: float = 0.5) -> tuple[float, ...]:
        """Incomes where the curve crosses `threshold` — the taper edges, made findable.

        Reported as the income of the point AFTER the crossing, because that is the first
        income at which the reader would actually face the new rate.
        """
        out = []
        for previous, current in zip(self.points, self.points[1:], strict=False):
            if (previous.emtr < threshold) != (current.emtr < threshold):
                out.append(current.salaire_brut_annuel)
        return tuple(out)


def sweep_frame(household_type: str, incomes: tuple[float, ...]) -> Any:
    """One household per income point, all of the same type, each weighted 1.

    Weight 1 and `synthetic=True` on every row: a sweep is a ruler, not a sample, and
    anything that read a distribution off it would be reading one off a ruler.
    """
    import polars as pl

    if household_type not in HOUSEHOLD_TYPES:
        raise ExplorerError(
            f"type de ménage inconnu : « {household_type} ». Les types offerts sont "
            f"{sorted(HOUSEHOLD_TYPES)}. Un EMTR est une propriété d'un MÉNAGE et pas "
            f"d'un revenu : à 24 000 EUR, un célibataire locataire et un couple avec "
            f"deux enfants ne sont pas au même endroit du paysage.")
    if not incomes:
        raise ExplorerError("une plage de revenus vide ne trace aucune courbe")

    spec = HOUSEHOLD_TYPES[household_type]
    rows: list[dict[str, Any]] = []
    person = 0
    for index, income in enumerate(incomes):
        household = f"SWEEP-{index:04d}"
        members: list[tuple[str, str, str, int, float]] = [
            ("personne_de_reference", "declarant_principal", "demandeur", 40, income)]
        if spec["adults"] == 2:
            members.append(("conjoint", "conjoint", "conjoint", 40, 0.0))
        for _ in range(spec["children"]):
            members.append(("enfant", "personne_a_charge", "enfant", 8, 0.0))
        for role_menage, role_foyer, role_famille, age, salary in members:
            rows.append({
                "person_id": person, "household_id": household,
                "foyer_id": f"{household}#0", "famille_id": f"{household}#0",
                "weight": 1.0, "age": age, "sex": "female",
                "region": "metropole", "role_menage": role_menage,
                "role_foyer": role_foyer, "role_famille": role_famille,
                "statut_activite": "employed" if salary > 0 else "inactive",
                "statut_occupation": spec["statut_occupation"],
                "zone_apl": spec["zone_apl"], "is_salarie": salary > 0,
                "pcs": None, "secteur_public": False,
                "quotite_travail": 1.0 if salary > 0 else 0.0,
                "parent_isole": spec["adults"] == 1 and spec["children"] > 0,
                "synthetic": True, "salaire_brut_annuel": float(salary),
                "pension_annuelle": 0.0, "chomage_annuel": 0.0,
                "loyer_mensuel": float(spec["loyer_mensuel"]),
            })
            person += 1
    return pl.DataFrame(rows)


def incomes(step: float = DEFAULT_STEP_EUR,
            maximum: float = DEFAULT_MAX_EUR) -> tuple[float, ...]:
    if step <= 0 or maximum <= 0:
        raise ExplorerError("pas et maximum doivent être strictement positifs")
    count = int(maximum // step)
    return tuple(step * (i + 1) for i in range(count))


def curve(household_type: str, year: int = 2024, *, reform: Any = None,
          step: float = DEFAULT_STEP_EUR, maximum: float = DEFAULT_MAX_EUR) -> Curve:
    """Sweep one household type. Four full-tier runs, not two per point.

    Delegates to `behavioural.emtr.compute`, which prices a whole frame in one pass and
    already refuses anything but the full tier — the taper of PPA and RSA is most of the
    marginal rate at low wages, and a light-tier curve would be tidy and wrong exactly
    where the argument lives (D-033).
    """
    from impots.behavioural import emtr as emtr_module

    grid = incomes(step, maximum)
    frame = sweep_frame(household_type, grid)
    result = emtr_module.compute(frame, year=year, reform=reform)
    households = result.households.sort("household_id")
    rates = households["emtr"].to_list()
    reformed = (households["emtr_reform"].to_list()
                if "emtr_reform" in households.columns else [None] * len(rates))
    if len(rates) != len(grid):
        raise ExplorerError(
            f"{len(rates)} taux pour {len(grid)} revenus : le balayage a perdu des "
            f"ménages en route, et une courbe à trous serait lue comme une courbe.")
    return Curve(
        household_type=household_type, label=HOUSEHOLD_TYPES[household_type]["label"],
        year=year,
        points=tuple(CurvePoint(salaire_brut_annuel=income, emtr=rate,
                                emtr_reform=reform_rate)
                     for income, rate, reform_rate in zip(grid, rates, reformed,
                                                          strict=True)),
        reform=(reform.model_dump(exclude_none=True, mode="json")
                if reform is not None and hasattr(reform, "model_dump") else None),
    )
