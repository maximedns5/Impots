"""La CVAE au barème entier, et le chemin qui la chiffre année par année (D-254).

La loi fait bouger le barème de la CVAE tout entier d'une année à l'autre — le taux
plafond, les pentes et les ordonnées de ses tranches, le dégrèvement complémentaire —, puis
l'abroge en 2030. `cvae_echelle` règle ce barème entier, pas sa seule tranche du haut : un
facteur sur le droit de l'année. Chaque cas est calculé à la main dans son test.
"""

from __future__ import annotations

import numpy as np
import pytest
from openfisca_core import periods
from openfisca_core.reforms import Reform
from openfisca_core.simulation_builder import SimulationBuilder
from pydantic import ValidationError

from exploration_cases import exploration_request
from impots.api.schemas import ExplorationRequest, PredictifRequest
from impots.entreprises import system as firm_system
from impots.entreprises.reforms import (
    CVAE_SCHEDULE,
    FirmReformSpec,
    law_moves,
    resolve,
    verify_scales,
)
from impots.parameters import create_parameter, update_existing


def _cvae(system, turnovers: list[float], vas: list[float], year: int = 2026) -> np.ndarray:
    builder = SimulationBuilder()
    builder.create_entities(system)
    builder.declare_person_entity("entreprise", np.arange(len(turnovers)))
    simulation = builder.build(system)
    period = str(year)
    simulation.set_input("chiffre_affaires", period, np.array(turnovers, dtype=np.float64))
    simulation.set_input("benefice_imposable", period, np.zeros(len(turnovers)))
    simulation.set_input("valeur_ajoutee", period, np.array(vas, dtype=np.float64))
    return simulation.calculate("cvae", period)


def _law(path: tuple[str, ...], year: int) -> float | None:
    return resolve(firm_system.baseline().parameters, path)(f"{year}-01-01")


# --------------------------------------------------------------------------- #
# the knob
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("year", [2026, 2029])
def test_the_scale_writes_the_whole_schedule_of_the_year(year: int) -> None:
    """Every rate of the schedule, and the dégrèvement, at half the year's law: in 2026,
    0,28 % becomes 0,14 % and 188 € becomes 94 € ; in 2029, 0,09 % becomes 0,045 %. The
    thresholds and the franchise are not rates, and stay where the law has them."""
    reformed = firm_system.reformed_for(FirmReformSpec(cvae_echelle=0.5), year)
    for path in CVAE_SCHEDULE:
        got = resolve(reformed.parameters, path)(f"{year}-01-01")
        assert got == pytest.approx(0.5 * _law(path, year), rel=1e-9), path
    for path in (("cvae", "franchise"), ("cvae", "bornes", "t3_t4"),
                 ("cvae", "plafond_va", "taux_haut")):
        assert resolve(reformed.parameters, path)(f"{year}-01-01") == _law(path, year)


def test_half_the_schedule_charges_what_the_hand_computes() -> None:
    """By hand, 2026, two firms.
    - 80 M€ of turnover and 20 M€ of value added, above the last threshold: the ceiling
      rate, unrounded, 0,0028 × 20 M€ = 56 000 €, and at half 28 000 €.
    - 1,9 M€ and 1,2 M€, under the dégrèvement's threshold: 0,094 % × 1,4 / 2,5 =
      0,05264 %, rounded to 0,05 %, 600 € less 188 € = 412 €. At half the schedule,
      0,047 % × 1,4 / 2,5 = 0,02632 %, rounded to 0,03 % — the law rounds the scaled
      rate, as it does when it moves its own —, 360 € less 94 € = 266 €."""
    firms = ([80e6, 1.9e6], [20e6, 1.2e6])
    law = _cvae(firm_system.baseline(), *firms)
    half = _cvae(firm_system.reformed_for(FirmReformSpec(cvae_echelle=0.5), 2026), *firms)
    assert law == pytest.approx([56_000.0, 412.0], rel=1e-5)
    assert half == pytest.approx([28_000.0, 266.0], rel=1e-5)


def test_no_schedule_is_no_cvae() -> None:
    firms = ([80e6, 6.2e6, 1.9e6], [20e6, 1.86e6, 1.2e6])
    nothing = _cvae(firm_system.reformed_for(FirmReformSpec(cvae_echelle=0.0), 2026), *firms)
    assert list(nothing) == [0.0, 0.0, 0.0]


def test_a_year_without_the_cvae_has_nothing_to_scale() -> None:
    """From 2030 the law has abolished the CVAE and its schedule is null: the factor
    finds nothing to move, writes nothing, and the CVAE stays at zero. Not a refusal —
    the annual path prices every year, and that year's answer is « nothing »."""
    reformed = firm_system.reformed_for(FirmReformSpec(cvae_echelle=0.5), 2030)
    for path in CVAE_SCHEDULE:
        assert resolve(reformed.parameters, path)("2030-01-01") is None, path
    assert list(_cvae(reformed, [80e6], [20e6], year=2030)) == [0.0]


@pytest.mark.parametrize("other", [{"cvae_taux_max": 0.002}, {"cvae_degrevement": 100.0}])
def test_the_scale_is_not_mixed_with_a_knob_it_already_moves(other: dict) -> None:
    """GUARD. The ceiling and the dégrèvement are in the schedule the factor scales: set
    both, and which one wins is the order of the writes, not a policy."""
    with pytest.raises(ValidationError, match="cvae_echelle"):
        FirmReformSpec(cvae_echelle=0.5, **other)


# --------------------------------------------------------------------------- #
# the read-back (D-007)
# --------------------------------------------------------------------------- #
def _reform(modify) -> object:
    class Broken(Reform):
        name = "cvae-broken"

        def apply(self) -> None:
            self.modify_parameters(modifier_function=modify)

    return Broken(firm_system.baseline())


def test_the_read_back_refuses_a_schedule_scaled_at_its_ceiling_only() -> None:
    """GUARD. D-250's step: the ceiling halved, the brackets below left at the law. A
    reform that applied the factor so would cut the top band alone, and open a cliff at
    50 M€; the read-back names what it left behind."""
    start = periods.instant("2026-01-01")

    def ceiling_only(parameters):
        update_existing(parameters, ("cvae", "taux_max"), start=start, value=0.0014,
                        instant="2026-01-01")
        return parameters

    with pytest.raises(AssertionError, match="pente_t1"):
        verify_scales(_reform(ceiling_only), FirmReformSpec(cvae_echelle=0.5), 2026)


def test_the_read_back_refuses_a_cvae_brought_back_where_the_law_has_none() -> None:
    """GUARD. A factor on an abolished schedule is nothing. A reform that wrote a rate
    there would tax what the law no longer taxes, and the read-back refuses it."""
    start = periods.instant("2030-01-01")

    def revived(parameters):
        create_parameter(parameters, ("cvae", "taux_max"), start=start, value=0.0014)
        return parameters

    with pytest.raises(AssertionError, match="taux_max"):
        verify_scales(_reform(revived), FirmReformSpec(cvae_echelle=0.5), 2030)


# --------------------------------------------------------------------------- #
# the carried path
# --------------------------------------------------------------------------- #
def test_the_law_moves_are_read_on_the_tree() -> None:
    """The CVAE's schedule changes in 2028 and is null from 2030; the IS normal rate does
    not move. Read on the parameter tree, not written here."""
    parameters = firm_system.baseline().parameters
    assert law_moves(FirmReformSpec(cvae_echelle=0.5), parameters, 2026, 2035) == {
        "cvae_echelle": 2028}
    assert law_moves(FirmReformSpec(cvae_taux_max=0.002), parameters, 2026, 2035) == {
        "cvae_taux_max": 2028}
    assert law_moves(FirmReformSpec(cvae_echelle=0.5), parameters, 2026, 2027) == {}
    assert law_moves(FirmReformSpec(is_taux_normal=0.24), parameters, 2026, 2035) == {}


PAYLOAD = {"spending": {"rule": "gele_en_volume"},
           "growth": {"name": "Croissance réelle 1 %, prix 2 %", "real": 0.01,
                      "prices": 0.02},
           "rate": {"name": "Taux implicite tenu à son niveau de 2025",
                    "kind": "implicite_tenu"},
           "theta": {"common": 0.5},
           "uprating": {"wage": 0.03, "source": "3 % ronds"}}


@pytest.mark.parametrize("firm", [{"cvae_echelle": 0.5}, {"cvae_taux_max": 0.002}])
def test_the_carried_path_refuses_a_law_that_moves_within_its_horizon(firm: dict) -> None:
    """GUARD. `/predictif/simulate` prices 2026 and carries it: over ten years, the
    CVAE's cost would be held at its 2026 law through the cut of 2028 and past its
    abolition in 2030. Refused, naming the year and the annual path."""
    with pytest.raises(ValidationError, match="2028") as caught:
        PredictifRequest.model_validate({**PAYLOAD, "firm_reform": firm, "horizon": 10})
    assert "impots predictif" in str(caught.value)


def test_the_carried_path_takes_a_law_that_holds_over_its_horizon() -> None:
    """Over 2026 and 2027 the CVAE's law is that of 2026; the IS rate holds throughout."""
    PredictifRequest.model_validate({**PAYLOAD, "firm_reform": {"cvae_echelle": 0.5},
                                     "horizon": 2})
    PredictifRequest.model_validate({**PAYLOAD, "firm_reform": {"is_taux_normal": 0.24},
                                     "horizon": 10})


@pytest.mark.parametrize("overrides", [
    {"bounds": [{"knob": "cvae_echelle", "low": 0.5, "high": 1.0, "step": 0.25}]},
    {"firm_base": {"cvae_taux_max": 0.002},
     "bounds": [{"knob": "is_taux_normal", "low": 0.24, "high": 0.25, "step": 0.01}]},
], ids=["grille", "base"])
def test_the_explorer_refuses_a_law_that_moves_within_its_horizon(overrides: dict) -> None:
    """GUARD. The explorer carries each bundle's first year the same way."""
    with pytest.raises(ValidationError, match="2028"):
        ExplorationRequest.model_validate(exploration_request(**overrides))


# --------------------------------------------------------------------------- #
# C4 and the annual path's note
# --------------------------------------------------------------------------- #
def test_c4_reads_the_whole_schedule() -> None:
    """C4's regressor is the log of the production tax: the factor moves it as the
    ceiling did."""
    from impots.behavioural.store import load

    assert load()["production_tax_investment"].claims("cvae_echelle")


def test_the_annual_path_says_when_the_cvae_is_gone() -> None:
    """A firm cost that falls to zero in 2030 is the law, not an error: the report's note
    names the year, read on the tree."""
    from impots.predictif import firmes

    note = firmes.extinction(FirmReformSpec(cvae_echelle=0.0), list(range(2026, 2036)))
    assert "2030" in note and "CVAE" in note
    assert firmes.extinction(FirmReformSpec(cvae_echelle=0.0), [2026, 2027]) is None
    assert firmes.extinction(FirmReformSpec(is_taux_normal=0.24),
                             list(range(2026, 2036))) is None


# --------------------------------------------------------------------------- #
# C4 at the ends of the scale
# --------------------------------------------------------------------------- #
def _c4(**taxes):
    from impots.behavioural import channels
    from impots.behavioural.store import load

    return channels.production_tax_investment(load(), FirmReformSpec(cvae_echelle=0.0),
                                              draws=4, rng=np.random.default_rng(0),
                                              **taxes)


def test_c4_says_an_abolition_has_no_log_to_read() -> None:
    """The regressor is the log of the production tax: from 3,28 Md€ to nothing is an
    infinite fall, beyond any study. Said, not priced and not a crash: the firm endpoint
    returned 500 on `cvae_echelle = 0` before."""
    result = _c4(production_tax_baseline=3.28e9, production_tax_reform=0.0)
    assert not result.applies and "suppression" in result.message


def test_c4_says_a_year_without_the_tax_has_nothing_to_answer() -> None:
    """In 2030 the law has no CVAE and the factor moves nothing."""
    result = _c4(production_tax_baseline=0.0, production_tax_reform=0.0)
    assert not result.applies and "2030" in result.message


def test_c4_without_its_inputs_still_fails_loudly() -> None:
    """GUARD. A claimed channel handed nothing is an input error, not a year without the
    tax: the two must not read alike."""
    from impots.behavioural import channels

    with pytest.raises(channels.ChannelInputMissing, match="strictly positive"):
        _c4()


def test_the_firm_band_takes_an_abolition() -> None:
    from impots.behavioural import band

    result = band.compute(mechanical=-3.28e9, reform=FirmReformSpec(cvae_echelle=0.0),
                          production_tax_baseline=3.28e9, production_tax_reform=0.0)
    c4 = next(c for c in result.channels if c["key"] == "c4_investment")
    assert not c4["applies"]
