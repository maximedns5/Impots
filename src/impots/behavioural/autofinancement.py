"""What a job at the SMIC brings the public finances in a year, measured (D-256).

C11 prices the self-financing of a targeted cut of employer contributions, and its low end
is C2's own jobs, valued one by one. The Trésor-Éco n° 97 values a job at 12 000 € of 2009
(note 5, p. 4): the contributions on a full-time SMIC, 6 500 €, and the RSA of a single
person without children, 5 500 €. The same case is measured here on the engine, in the
year of the reform, rather than carried from 2009: since then the allègements have taken
most of the employer contributions at the SMIC, and the prime d'activité pays a SMIC
earner what the RSA paid the jobless.

A single person born in 1985, no child, no rent declared, at a full-time SMIC against the
same person without earnings. What the job brings is its cost to the employer less what it
adds to the household's disposable income: the contributions on both sides, the CSG, the
CRDS and the income tax it pays, the RSA it saves, less the prime d'activité it opens.
10 032 € in 2026, 45 % of the job's cost.
"""

from __future__ import annotations

from functools import cache


class JobValueError(ValueError):
    """The engine returned a job value no reading could use."""


@cache
def job_value(year: int) -> float:
    """Euros a full-time SMIC job brings the public finances in `year` (module docstring)."""
    from impots import service
    from impots.api.schemas import HouseholdInput
    from impots.engine import compute

    def rows(gross: float) -> dict[str, float]:
        household = HouseholdInput.model_validate({
            "adults": [{"salaire_brut_annuel": gross, "annee_naissance": 1985}]})
        return compute(household, year, tier="full").baseline

    at_work, without = rows(service.smic_annual(year)), rows(0.0)
    cost = at_work["salaire_super_brut"]
    value = cost - (at_work["revenu_disponible"] - without["revenu_disponible"])
    if not 0.0 < value < cost:
        raise JobValueError(
            f"un emploi au SMIC rapporterait {value:,.0f} € pour un coût de {cost:,.0f} € en "
            f"{year} : hors de ]0 ; coût[, aucune lecture de l'autofinancement ne s'en sert")
    return float(value)
