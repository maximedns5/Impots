"""PLF 2027 art. 74 (D-298) : les deux revalorisations que l'article suspend, à leur date.

L'article ne revalorise en 2027 ni le montant forfaitaire de la prime d'activité, au
1er avril (CSS L. 842-3, sixième alinéa), ni les paramètres de dépense de logement des
aides personnelles, au 1er octobre (CCH L. 823-4). L'arbre est figé en 2026 et ne porte
aucune des deux : le cas chiffre donc la revalorisation, en miroir, et l'article est son
opposé.

Un bouton de revalorisation est un COEFFICIENT sur ce que l'arbre porte à la date légale,
écrit à partir du premier jour de ce mois dans l'année chiffrée, jamais du 1er janvier :
écrit dès janvier, le bouton d'avril compterait trois mois de trop et celui d'octobre neuf.
Ces tests le tiennent par le mois, sur un ménage, et par la relecture de l'arbre, contre
des écritures fautives qu'ils plantent eux-mêmes.
"""

from __future__ import annotations

import pydantic
import pytest

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import reforms, situations
from impots.engine.compute import _build
from impots.engine.system import baseline, clear_cache, reformed_for
from impots.parameters import resolve, update_existing

pytestmark = pytest.mark.slow

YEAR = 2026
#: Seul, au-dessus du forfait : sa prime suit le montant forfaitaire, euro pour euro.
SEUL_AU_DESSUS_DU_FORFAIT = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 15000, "annee_naissance": 1990}]})
#: Zone 2, comme la population (D-297) : un loyer au-dessus du plafond, qui revalorisé
#: relève l'aide.
LOCATAIRE = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 11000, "annee_naissance": 1990}],
     "children": [{"annee_naissance": 2015}],
     "logement": {"statut": "locataire_vide", "loyer_mensuel": 600, "zone_apl": 2}})
BOTH = {"ppa_revalorisation_avril": 1.021, "al_revalorisation_octobre": 1.020}


def _months(household: HouseholdInput, spec: ReformSpec | None, variable: str):
    system = reformed_for(spec, YEAR) if spec is not None else baseline()
    situation = situations.build_situation(household, YEAR, True)
    simulation = _build(system, situation, YEAR, "full")
    return [float(simulation.calculate(variable, f"{YEAR}-{m:02d}").sum())
            for m in range(1, 13)]


def _day_before(year: int, month: int) -> str:
    return f"{year}-{month - 1:02d}-28"


# --- the October set, read off the tree ----------------------------------------------


def test_the_october_set_is_read_off_the_tree_and_moved_by_the_irl():
    """Every leaf the October 2025 revision moved, and nothing else.

    Derived, not listed: 56 leaves under `aides_logement` carry a value dated
    2025-10-01, and every one of them moved by the IRL of the second quarter of 2025,
    +1,04 %, rounded to the cent. The 5 EUR minoration of 2017 is not revised, and is not
    in the set.
    """
    paths = reforms.al_parametres_revises_en_octobre(YEAR)
    parameters = baseline().parameters
    assert len(paths) == 56
    for path in paths:
        assert path[:2] == ("prestations_sociales", "aides_logement")
        ratio = (float(resolve(parameters, path)("2025-10-01"))
                 / float(resolve(parameters, path)("2025-09-30")))
        assert 1.0100 <= ratio <= 1.0110, (path, ratio)
    names = {".".join(p[-3:]) for p in paths}
    assert "zone_2.personnes_seules" in {".".join(p[-2:]) for p in paths}
    assert "p0_particip_min.p0_forfait" in {".".join(p[-2:]) for p in paths}
    assert "c_forfait_charges.cas_general.cas_general" in names
    assert tuple(reforms.PATH_AL_MINORATION) not in paths


# --- what a household sees, month by month ------------------------------------------


def test_the_ppa_coefficient_moves_nothing_before_april_and_all_of_it_from_july():
    """Measured, and a bias the prognosis declares (D-298): the engine averages the prime
    over its reference quarter with each month's forfait, so April does not move, May
    takes a third of the revaluation, June two thirds, and July onward all of it: seven
    month-equivalents of the nine the law counts from April.

    On a household whose resources exceed the forfait, which is where the prime follows
    it: below it, the prime is 59,85 % of the earnings plus the bonification, and the
    forfait does not enter (measured on the part-time parent of `knob_cases`: a few cents).
    """
    before = _months(SEUL_AU_DESSUS_DU_FORFAIT, None, "ppa")
    after = _months(SEUL_AU_DESSUS_DU_FORFAIT, ReformSpec(ppa_revalorisation_avril=1.021),
                    "ppa")
    moved = [a - b for a, b in zip(after, before, strict=True)]
    assert before[3] > 0, "le ménage ne touche pas la prime : rien n'est prouvé"
    assert moved[:4] == pytest.approx([0.0] * 4, abs=1e-6)
    full = moved[6]
    assert full > 10.0
    assert moved[6:] == pytest.approx([full] * 6, rel=0.01)
    assert 0 < moved[4] < moved[5] < full


def test_the_housing_coefficient_moves_october_to_december_and_nothing_before():
    before = _months(LOCATAIRE, None, "aide_logement")
    after = _months(LOCATAIRE, ReformSpec(al_revalorisation_octobre=1.020),
                    "aide_logement")
    assert before[9] > 0, "le ménage ne touche pas l'aide : rien n'est prouvé"
    assert after[:9] == pytest.approx(before[:9], abs=1e-6)
    assert all(a > b + 0.5 for a, b in zip(after[9:], before[9:], strict=True))


# --- the tree, read back -------------------------------------------------------------


def test_the_coefficient_multiplies_what_the_tree_carries_at_its_date_and_only_then():
    system = reformed_for(ReformSpec(**BOTH), YEAR)
    reference = baseline().parameters
    for knob, month in reforms.REVALORISATION_KNOBS.items():
        date = f"{YEAR}-{month:02d}-01"
        for path in reforms.revalorisation_paths(knob, YEAR):
            want = float(resolve(reference, path)(date)) * BOTH[knob]
            assert float(resolve(system.parameters, path)(date)) == pytest.approx(want)
            assert float(resolve(system.parameters, path)(_day_before(YEAR, month))) \
                == float(resolve(reference, path)(_day_before(YEAR, month)))


def _write(parameters, path, date, value):
    update_existing(parameters, path, start=reforms.periods.instant(date), value=value,
                    instant=date)


def _from_january(parameters, knob, coefficient, year):
    month = reforms.REVALORISATION_KNOBS[knob]
    for path in reforms.revalorisation_paths(knob, year):
        value = float(resolve(parameters, path)(f"{year}-{month:02d}-01"))
        _write(parameters, path, f"{year}-01-01", value * coefficient)


def _one_left_out(parameters, knob, coefficient, year):
    month = reforms.REVALORISATION_KNOBS[knob]
    date = f"{year}-{month:02d}-01"
    for path in reforms.revalorisation_paths(knob, year)[:-1]:
        _write(parameters, path, date, float(resolve(parameters, path)(date)) * coefficient)


def _squared(parameters, knob, coefficient, year):
    month = reforms.REVALORISATION_KNOBS[knob]
    date = f"{year}-{month:02d}-01"
    for path in reforms.revalorisation_paths(knob, year):
        _write(parameters, path, date,
               float(resolve(parameters, path)(date)) * coefficient ** 2)


@pytest.mark.parametrize("writer, knob, needle", [
    (_from_january, "ppa_revalorisation_avril", "avant"),
    (_from_january, "al_revalorisation_octobre", "avant"),
    (_one_left_out, "al_revalorisation_octobre", "al_revalorisation_octobre"),
    (_squared, "ppa_revalorisation_avril", "demandé"),
])
def test_the_read_back_refuses_a_faulty_write(monkeypatch, writer, knob, needle):
    """Each fault is planted in the writer; the read-back, which derives what it expects
    from the baseline tree and the legal month on its own, must refuse every one."""
    monkeypatch.setattr(reforms, "_apply_revalorisation", writer)
    spec = ReformSpec(**{knob: BOTH[knob]})
    system = reforms.make_reform(spec, YEAR, "faute")(baseline())
    with pytest.raises(AssertionError, match=needle):
        reforms.verify_revalorisations(system, spec, YEAR)


def test_the_read_back_refuses_a_revaluation_with_nothing_to_revalue(monkeypatch):
    """An empty set — a tree whose last revision fell on another date — would write
    nothing and read nothing back, and a coefficient of 1,02 would price at zero."""
    monkeypatch.setattr(reforms, "revalorisation_paths", lambda knob, year: ())
    spec = ReformSpec(al_revalorisation_octobre=1.020)
    system = reforms.make_reform(spec, YEAR, "vide")(baseline())
    with pytest.raises(AssertionError, match="aucun paramètre"):
        reforms.verify_revalorisations(system, spec, YEAR)


def test_the_reformed_system_runs_the_read_back(monkeypatch):
    """Fails if `system.reformed` stops calling `verify_revalorisations`: a read-back no
    caller runs guards nothing."""
    monkeypatch.setattr(reforms, "_apply_revalorisation", _from_january)
    clear_cache()
    try:
        with pytest.raises(AssertionError, match="avant"):
            reformed_for(ReformSpec(ppa_revalorisation_avril=1.021), YEAR)
    finally:
        clear_cache()


# --- the wire model ------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.0, 0.4, 2.5])
def test_a_coefficient_outside_its_bounds_is_refused(value):
    with pytest.raises(pydantic.ValidationError):
        ReformSpec(ppa_revalorisation_avril=value)
    with pytest.raises(pydantic.ValidationError):
        ReformSpec(al_revalorisation_octobre=value)


def test_a_level_and_an_april_revaluation_of_the_ppa_together_are_refused():
    """The level is written from January and the revaluation reads the April value: the
    two together would revalue the level asked for, which neither knob says alone."""
    with pytest.raises(pydantic.ValidationError, match="ppa_revalorisation_avril"):
        ReformSpec(ppa_montant_de_base=650.0, ppa_revalorisation_avril=1.021)
