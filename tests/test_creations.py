"""Phase 9 M5 — company creations (§6.3) and the IS's investment channel (§6.2), D-221.

What is held here: the IPP's Tableau 2.2 is read inside its panel (b), never from the
three other panels that print an IS-PFU row of their own; the figure the authors quote
is found among the cells by value, so a reading that drifted to another panel fails
loudly; and the closed channel for the IS and investment says what was read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from impots.behavioural import ipp


def _report() -> ipp.Reading:
    pytest.importorskip("pypdf")
    if not (ipp.RAW / ipp.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le rapport IPP n° 47 — les sources primaires ne "
                    "sont pas versionnées")
    return ipp.load()


# --------------------------------------------------------------------------- #
# Reading the report
# --------------------------------------------------------------------------- #
def test_the_joint_cells_are_the_ones_printed_in_panel_b() -> None:
    """Pinned by eye off Tableau 2.2 (PDF p. 62). Panel (a), the binary exposure, prints
    0,021 (0,005) in the same row: a reader one panel off is wrong by a factor of
    twenty and would still look like a coefficient."""
    reading = _report()
    assert [(c.estimate, c.se) for c in reading.joint] == [
        (0.391, 0.120), (0.380, 0.131), (0.418, 0.120), (0.414, 0.137)]
    assert reading.table_page == 62
    assert reading.quoted == 0.38
    assert reading.mean_is_exposure == 5.4
    assert reading.pfu_rate == 0.30


#: Tableau 2.2 cut down: the same row in panels (a), (b) and (c).
TABLE = ["TABLEAU 2.2 – Estimations statiques",
         "tions (a) Exposition binaire aux réformes",
         "IS-PFU 0.021*** 0.020***", "(0.005) (0.004)",
         "(b) Exposition linéaire aux réformes",
         "IS 0.571*** 0.123", "(0.192) (0.188)",
         "IS-PFU 0.391*** 0.380***", "(0.120) (0.131)",
         "(c) Exposition linéaire pondérée par emploi",
         "IS-PFU 0.046*** 0.053***", "(0.014) (0.015)"]


def test_the_row_is_read_inside_panel_b_and_never_from_another() -> None:
    """GUARD. Read from the first IS-PFU line of the page, the reader hands back panel
    (a)'s binary coefficients; read past panel (b)'s end, panel (c)'s employment ones."""
    assert ipp._joint(TABLE) == (ipp.Coefficient(0.391, 0.120), ipp.Coefficient(0.380, 0.131))
    without = [line for line in TABLE if not line.startswith(("IS-PFU 0.39", "(0.120)"))]
    with pytest.raises(ipp.IppError, match="introuvable"):
        ipp._joint(without)


def test_the_quoted_figure_must_be_one_of_the_cells_read() -> None:
    """GUARD. Panel (a)'s cells do not contain the authors' 0,38: a drifted reading is
    refused here, not loaded."""
    panel_b = ipp._joint(TABLE)
    assert ipp._quoted_among(0.38, panel_b) == 0.38
    panel_a = (ipp.Coefficient(0.021, 0.005), ipp.Coefficient(0.020, 0.004))
    with pytest.raises(ipp.IppError, match="aucune cellule"):
        ipp._quoted_among(0.38, panel_a)


def test_a_missing_report_names_the_manifest_rather_than_returning_nothing(
        tmp_path: Path) -> None:
    with pytest.raises(ipp.IppError, match="impots data fetch"):
        ipp.load(tmp_path)


# --------------------------------------------------------------------------- #
# §6.2: the IS and investment stay closed, and say what was read
# --------------------------------------------------------------------------- #
def test_the_closed_is_channel_says_the_2023_report_was_read() -> None:
    from impots.predictif import chaine

    reason = chaine.CLOSED["IS et investissement des entreprises"]
    assert "France Stratégie, 2023" in reason and "D-221" in reason


# --------------------------------------------------------------------------- #
# §6.3: the two rows, against the reports
# --------------------------------------------------------------------------- #
def test_the_conversion_is_the_hand_derived_one() -> None:
    """Derived by hand: 5,4 / (33,33 − 25) × (1 − 0,30) = 5,4 / 8,33 × 0,7 = 0,45378."""
    reading = ipp.Reading(joint=(ipp.Coefficient(0.38, 0.131),), quoted=0.38,
                          mean_is_exposure=5.4, pfu_rate=0.30, table_page=62)
    assert ipp.exposure_per_is_point(reading, (33.33, 25.0)) == pytest.approx(
        0.453781512605, abs=1e-12)


def test_the_convention_puts_the_bottom_at_zero_and_the_top_at_the_widest_interval() -> None:
    """Derived by hand from the four printed cells: the top is column 12's,
    0,414 + 0,0005 + 1,96 × (0,137 + 0,0005) = 0,684; the centre the quoted 0,38; the
    bottom zero, because the IS is not told apart from the flat tax."""
    reading = ipp.Reading(
        joint=(ipp.Coefficient(0.391, 0.120), ipp.Coefficient(0.380, 0.131),
               ipp.Coefficient(0.418, 0.120), ipp.Coefficient(0.414, 0.137)),
        quoted=0.38, mean_is_exposure=5.4, pfu_rate=0.30, table_page=62)
    assert ipp.convention(reading) == ipp.Range(low=0.0, central=0.38, high=0.684)


def test_the_store_rows_are_the_reports_read_through_the_convention() -> None:
    """The YAML against the PDFs: a retyped digit, or a cell the reader stopped finding,
    fails here."""
    from impots.behavioural.store import load

    reading = _report()
    if not (ipp.RAW / ipp.FS_FILE).exists():
        pytest.skip("data/raw/ n'a pas le rapport final de France Stratégie")
    store = load()
    expected = ipp.convention(reading)
    row = store["firm_creation_profit_tax"]
    assert (row.low, row.central, row.high) == (expected.low, expected.central,
                                                expected.high)
    assert ipp.statutory_cut() == (33.33, 25.0)
    conversion = store["firm_creation_exposure_per_is_point"]
    assert not conversion.is_open
    assert conversion.central == pytest.approx(
        ipp.exposure_per_is_point(reading, ipp.statutory_cut()), abs=5e-5)


# --------------------------------------------------------------------------- #
# C8, an index and never revenue
# --------------------------------------------------------------------------- #
class Reform:
    def __init__(self, **knobs) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True, **_) -> dict:
        return dict(self._knobs)


IS_UP = Reform(is_taux_normal=0.26)


def _fixed(coefficient: float):
    from impots.behavioural import channels
    from impots.behavioural.store import Parameter, Source, Store, Support, Verifier

    def row(key: str, value: float) -> Parameter:
        return Parameter(
            key=key, central=value, low=value, high=value, applies_to="test",
            support=Support(estimated_on="test", max_variation_graded_in_support=0.0),
            source=Source(citation="test"), verifier=Verifier(verdict="CONFIRMED"),
            responds_to_knobs=("is_taux_normal",))
    return Store(parameters={channels.C8_KEYS[0]: row(channels.C8_KEYS[0], coefficient),
                             channels.C8_CONVERSION: row(channels.C8_CONVERSION, 0.4538)})


def test_c8_reproduces_the_worked_example() -> None:
    """Derived by hand: +1 point of IS normal rate is 0,4538 point of virtual rate, and
    at 0,38 the creation rate loses 0,38 × 0,4538 = 0,172444 point. A cut of 2 points
    gains twice as much, and is the direction the paper observed."""
    import numpy as np

    from impots.behavioural import channels

    rise = channels.firm_creations(_fixed(0.38), IS_UP, is_rate_change_points=1.0,
                                   draws=1, rng=np.random.default_rng(0))
    assert rise.applies and not rise.in_revenue_band
    assert rise.draws[0] == pytest.approx(-0.172444, abs=1e-9)
    assert rise.diagnostics["rests_on_symmetry"] is True
    cut = channels.firm_creations(_fixed(0.38), Reform(is_taux_normal=0.23),
                                  is_rate_change_points=-2.0, draws=1,
                                  rng=np.random.default_rng(0))
    assert cut.draws[0] == pytest.approx(2 * 0.172444, abs=1e-9)
    assert cut.diagnostics["rests_on_symmetry"] is False


def test_c8_opens_for_the_normal_rate_only() -> None:
    """GUARD. The paper observed the normal rate's cut; the reduced rate, the PME
    ceiling and the production taxes are other instruments."""
    import numpy as np

    from impots.behavioural import channels
    from impots.behavioural.store import load

    store = load()
    for knob in ("is_taux_reduit", "is_plafond_taux_reduit", "cvae_taux_max", "ir_bareme"):
        result = channels.firm_creations(store, Reform(**{knob: 0.1}),
                                         is_rate_change_points=1.0, draws=1,
                                         rng=np.random.default_rng(0))
        assert not result.applies and result.message == channels.NO_CREATION_KNOB, knob
    assert sorted(p.key for p in store.for_knob("is_taux_normal")) == [
        "firm_creation_exposure_per_is_point", "firm_creation_profit_tax"]


def test_c8_never_enters_the_revenue_band_and_is_always_illustrative() -> None:
    """GUARD. Points of a creation rate are not euros: the revenue band of an IS reform
    stays the mechanical figure's. And the support is zero: a national change of any
    size extrapolates a relative estimate."""
    from impots.behavioural import band

    result = band.compute(mechanical=-1e9, reform=IS_UP, store=_fixed(0.38),
                          is_rate_change_points=0.5, draws=20)
    assert result.band is None
    assert result.grade == "illustrative"
    creations = next(c for c in result.channels if c["key"] == "c8_creations")
    assert creations["applies"] and creations["grade"] == "illustrative"


def test_c8_without_the_rate_change_says_so() -> None:
    from impots.behavioural import channels

    quiet = channels.firm_creations(_fixed(0.38), IS_UP)
    assert not quiet.applies and quiet.message.startswith("Non calculé")


def test_a_channel_band_carries_the_channel_unit_not_euros() -> None:
    """GUARD. A band of points of creation rate labelled EUR reads as euros of revenue;
    the schema's default unit did that to C4 and C8 alike."""
    from impots.api.schemas import Behavioural
    from impots.behavioural import band

    result = band.compute(mechanical=-1e9, reform=IS_UP, store=_fixed(0.38),
                          is_rate_change_points=1.0, draws=20)
    payload = Behavioural(**result.as_dict())
    creations = next(c for c in payload.channels if c.key == "c8_creations")
    assert creations.band.unit == creations.unit == "points de taux de création"
