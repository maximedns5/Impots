"""F4 — the fiche de chiffrage generator.

The load-bearing tests are the three rules the renderer exists to enforce: a mechanical
figure never appears without its band or the reason there is none; the fan never renders
without its assumptions strip; and a section a model cannot fill is MARKED, not omitted.
Each has a kill test, because a report generator is exactly where a bare number creeps
back in — it renders more neatly than a qualified one.
"""

from __future__ import annotations

import pytest

from impots import fiche
from impots.api.schemas import (
    Behavioural,
    BehaviouralBand,
    BehaviouralChannel,
    DecileRow,
    Macro,
    MacroAssumptions,
    MacroQuantiles,
    NarrowBandFlag,
    PopulationMeta,
    PopulationResponse,
)
from impots.reporting import THIN_SPACE

PROVENANCE = fiche.Provenance(
    titre="Essai", source="variante interne", date="2026-09-08", scenario="essai")


def meta(**overrides) -> PopulationMeta:
    base = dict(vintage="2024", branch="A' — structure EEC, revenus synthétiques",
                households=31_013_334.0, persons=67_574_670.0, tier="quick",
                sampled_households=20_000, note="", limitations=["Aucun revenu observé."])
    return PopulationMeta(**{**base, **overrides})


def response(**overrides) -> PopulationResponse:
    base = dict(meta=meta(), totals={}, reform_cost=3.78e9,
                deciles=[DecileRow(decile=1, n_households=3_102_004.0,
                                   mean_niveau_de_vie=8_084.0, mean_baseline=0.0,
                                   mean_reform=0.0, mean_delta=792.0,
                                   share_winners=0.77, share_losers=0.0,
                                   share_unaffected=0.23)])
    return PopulationResponse(**{**base, **overrides})


def band_block(**overrides) -> Behavioural:
    base = dict(mechanical=-3.78e9,
                band=BehaviouralBand(p10=-4.2e9, p50=-3.8e9, p90=-3.3e9, unit="EUR"),
                grade="illustrative", grade_reason="Un canal hors support.",
                channels=[BehaviouralChannel(
                    key="c1", label="Offre de travail", applies=True, central=0.12,
                    band=BehaviouralBand(p10=0.04, p50=0.12, p90=0.21, unit="%"),
                    unit="%", message="", grade="in-support", diagnostics={})],
                seed=7, draws=2000, parameters_vintage="2026-09")
    return Behavioural(**{**base, **overrides})


def fan_block(**overrides) -> Macro:
    strip = MacroAssumptions(
        cycle_state="bas de cycle", design="transferts", leakage=0.22,
        leakage_applied=True, horizons=["1 an", "2 ans"], parameters_vintage="2026-09",
        grade="illustratif", covered_share=0.87, instruments=["rsa"],
        simulation_conditions="", caveats=["Pas une prévision."], banner="Bandeau.")
    base = dict(available=True,
                gdp={"1 an": MacroQuantiles(p10=0.01, p50=0.04, p90=0.08, unit="% PIB")},
                jobs={"1 an": MacroQuantiles(p10=2.0, p50=9.0, p90=17.0, unit="milliers")},
                assumptions=strip, uncovered={})
    return Macro(**{**base, **overrides})


# --------------------------------------------------------------------------- #
# Rule 1 — a mechanical figure never appears alone
# --------------------------------------------------------------------------- #


def test_a_mechanical_figure_with_no_band_says_there_is_none():
    """Fails if the renderer prints the cost and simply omits the behavioural block.

    A bare point estimate is the one thing this project exists not to publish, and a
    generator is where it creeps back in because a naked number renders more neatly.
    """
    text = fiche.render(response(behavioural=None), PROVENANCE)
    assert "+3,78 Md€" in text
    assert "Bande comportementale : absente" in text
    assert "il suppose que personne ne change de comportement" in text


def test_a_band_that_could_not_be_computed_gives_its_reason():
    """A band of None is not a band of zero, and the difference must be on the page."""
    text = fiche.render(
        response(behavioural=band_block(band=None,
                                        grade_reason="Aucun canal ne couvre cet instrument.")),
        PROVENANCE)
    assert "Aucun canal ne couvre cet instrument." in text
    assert "Une bande absente n'est pas une bande nulle" in text


def test_a_band_renders_with_its_grade_and_its_channels():
    text = fiche.render(response(behavioural=band_block()), PROVENANCE)
    assert "grade **illustrative**" in text
    assert "Offre de travail" in text
    assert "Un canal hors support." in text
    assert "graine 7" in text


def test_a_band_whose_channels_all_sleep_says_so_rather_than_printing_an_empty_table():
    """An empty table reads as «no effect»; the sentence says «no channel applies», which
    is a different claim. Fails if the renderer prints headers with no rows."""
    quiet = band_block(channels=[BehaviouralChannel(
        key="c1", label="X", applies=False, central=0.0, band=None, unit="%",
        message="", grade="no-evidence", diagnostics={})])
    text = fiche.render(response(behavioural=quiet), PROVENANCE)
    assert "Aucun canal ne s'applique" in text
    assert "| canal | central |" not in text


# --------------------------------------------------------------------------- #
# Rule 2 — the fan never renders without its strip
# --------------------------------------------------------------------------- #


def test_the_fiche_refuses_a_fan_without_its_assumptions_strip():
    """THE kill test for rule 2. Fails if the renderer prints quantiles when
    `assumptions` is None.

    The wire model already makes the strip mandatory on the macro block rather than
    optional, and the UI has its own version of this test. The fiche is the third
    surface and must not be the weak one: an unstripped fan reads as a forecast.
    """
    naked = Macro.model_construct(
        available=True,
        gdp={"1 an": MacroQuantiles(p10=0.01, p50=0.04, p90=0.08, unit="% PIB")},
        jobs={}, assumptions=None, uncovered={}, decomposition=[], composition=[],
        notes=[], unavailable_because="")
    with pytest.raises(fiche.FicheError, match="bandeau"):
        fiche.render(response(macro=naked), PROVENANCE)


def test_a_fan_renders_with_its_strip():
    text = fiche.render(response(macro=fan_block()), PROVENANCE)
    assert "bas de cycle" in text
    assert f"fuite 22{THIN_SPACE}%" in text, "typographie française attendue"
    assert "**PIB, 1 an**" in text
    assert "Pas une prévision." in text


def test_a_refused_fan_prints_the_refusal_verbatim():
    """The macro layer's refusals are informative — «this instrument is neither mapped
    nor listed as unmapped» tells a reader exactly what is missing. Fails if the fiche
    swallows the reason and prints a generic «non disponible»."""
    refused = Macro(available=False,
                    unavailable_because="delta 'aefa' n'est ni mappé ni listé.")
    text = fiche.render(response(macro=refused), PROVENANCE)
    assert "delta 'aefa' n'est ni mappé ni listé." in text
    assert "Un refus est ici un résultat" in text


# --------------------------------------------------------------------------- #
# Rule 3 — sections we cannot fill are marked, not omitted
# --------------------------------------------------------------------------- #


#: Written out, NOT read from `fiche.NOT_OURS`. Parametrizing over the collection under
#: test means emptying that collection deletes its own test cases: verified by doing it —
#: `NOT_OURS = ()` left all 26 tests green while the fiche silently dropped every declined
#: section. This is the D-044 shape, and it is the SECOND time it appeared in this
#: session's tests after being fixed once in `test_scenarios.py`. A check derived from
#: the thing it checks cannot fail when that thing is wrong.
SECTIONS_DECLINED = ("1", "2", "3", "5")


def test_the_declined_sections_are_the_four_expected_ones():
    """Fails if a section is added to or removed from `NOT_OURS` without a decision."""
    assert tuple(n for n, _t, _w in fiche.NOT_OURS) == SECTIONS_DECLINED


@pytest.mark.parametrize("numero", SECTIONS_DECLINED)
def test_every_section_a_model_cannot_write_is_printed_with_its_reason(numero):
    """Fails if a section is dropped instead of declined.

    A document that silently omits sections 1, 2, 3 and 5 LOOKS like a complete
    évaluation préalable, and a reader would reasonably assume the missing judgement had
    been made. Printing them with the reason is the difference between a costing and a
    counterfeit.
    """
    text = fiche.render(response(), PROVENANCE)
    assert f"**{numero}. " in text, f"section {numero} omise au lieu d'être déclinée"
    assert "ressemblerait" in text, "l'explication du refus a disparu"


def test_the_fiche_says_it_is_not_an_official_document():
    text = fiche.render(response(), PROVENANCE)
    assert "n'est pas une évaluation préalable et n'en tient pas lieu" in text


def test_a_response_with_no_reform_is_refused():
    """A baseline is not a costing. Fails if the renderer emits a fiche whose budget
    section has nothing in it."""
    with pytest.raises(fiche.FicheError, match="pas une réforme"):
        fiche.render(response(reform_cost=None), PROVENANCE)


# --------------------------------------------------------------------------- #
# Formatting — both bugs found while rendering a real response
# --------------------------------------------------------------------------- #


def test_number_formatting_does_not_eat_the_prose():
    """The first version applied `.replace(",", …)` to whole f-strings.

    «A' — EEC household structure, synthetic incomes (D-012), millésime 2024» came out
    with its clause commas turned into thousands separators. Fails if any call site goes
    back to scrubbing a whole sentence.
    """
    text = fiche.render(response(), PROVENANCE)
    assert "structure EEC, revenus synthétiques" in text, "les virgules de prose ont sauté"
    assert f"31{THIN_SPACE}013{THIN_SPACE}334 ménages" in text


def test_a_delta_keeps_its_sign():
    """On a delta column «792 €» and «-792 €» are a gain and a loss. Fails if the «+»
    is dropped and the reader has to supply it from context."""
    assert fiche._eur(792.0).startswith("+")
    assert fiche._eur(-792.0).startswith("-")
    text = fiche.render(response(), PROVENANCE)
    assert "+792 €" in text
    assert f"77{THIN_SPACE}%" in text, "les parts aussi en typographie française"


def test_magnitudes_are_rendered_in_the_right_unit():
    assert "Md€" in fiche._eur(3.78e9)
    assert "M€" in fiche._eur(1.2e6)
    assert fiche._eur(None) == "n. d."


def test_warnings_are_printed_when_they_fire_and_their_absence_is_stated():
    """Silence about a warning is indistinguishable from the warning not firing, so the
    absence is written out."""
    quiet = fiche.render(response(), PROVENANCE)
    assert "Aucun avertissement déclenché" in quiet

    flagged = NarrowBandFlag(share=0.004, flagged=True, window=500.0,
                             share_threshold=0.01, thresholds=[1000.0],
                             caveat="Résultat porté par peu de foyers.")
    loud = fiche.render(response(narrow_band=flagged), PROVENANCE)
    assert "Bande étroite" in loud and "Résultat porté par peu de foyers." in loud


def test_the_method_section_marks_calibration_lines_as_spent():
    """A calibrated line fits by construction and can never evidence correctness. Fails
    if the fiche prints reconciliation without saying which lines are spent."""
    text = fiche.render(response(), PROVENANCE)
    assert "Limites connues de la population" in text
    assert "Aucun revenu observé." in text


def test_the_follow_up_section_distinguishes_pre_registered_from_not():
    """A chiffrage produced without a declared tolerance is a calculation, not a
    prediction, and the fiche must not let the two look alike."""
    plain = fiche.render(response(), PROVENANCE)
    assert "n'est pas préenregistré" in plain

    registered = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-08", commit="abc1234", preregistre=True))
    assert "est **préenregistré** au commit `abc1234`" in registered


def test_channels_are_printed_even_when_the_overall_band_is_withheld():
    """Found by rendering a live response, not by reading the code.

    An employer-allègement reform produces NO overall band — it is larger than the
    interval the elasticities were estimated on, so the grade is «illustrative» and the
    band is withheld — while two channels fire WITH bands of their own, one of them
    +17 113 jobs [15 056 ; 19 093]. The first version nested the channel table inside
    the band branch, so the reader got «no band» and nothing else. Withholding what was
    computed understates as badly as a bare point estimate overstates.

    Fails if the table goes back inside the band branch.
    """
    withheld = band_block(
        band=None,
        grade_reason="Réforme plus grande que le support des élasticités.")
    text = fiche.render(response(behavioural=withheld), PROVENANCE)
    assert "aucune, et la raison est donnée" in text
    assert "| canal | central | bande | grade |" in text
    assert "Offre de travail" in text
    assert "n'est pas une bande de réforme" in text, (
        "un lecteur pourrait additionner les bandes de canaux ou les prendre pour la "
        "bande d'ensemble ; il faut le dire")


NB = THIN_SPACE


@pytest.mark.parametrize("value,unit,expected", [
    (9_770_165_637.0, "EUR", "+9,77 Md€"),
    (-46_647_408.0, "EUR", "-47 M€"),
    (17_113.1, "emplois", f"+17{NB}113 emplois"),
    (0.12, "%", "+0,12 %"),
    (None, "EUR", "—"),
])
def test_channel_quantities_are_readable_in_their_own_unit(value, unit, expected):
    """`:.4g` turned 9 770 165 637 into «9.77e+09» — scientific notation, in a French
    document, about euros. Fails if a channel figure goes back to a raw format spec."""
    assert fiche._quantity(value, unit) == expected


def test_french_decimals_and_thousands_do_not_collide():
    """Python writes «1,234.56»; French wants «1 234,56». Swapping in place would turn
    the thousands comma into a second decimal comma and give «1 234 56»."""
    assert fiche._num(1_234_567.89, 2) == f"1{THIN_SPACE}234{THIN_SPACE}567,89"
    assert fiche._num(999.5, 0) == "1 000".replace(" ", THIN_SPACE)


# --- F3 M5 (S2): the fiche extended to trajectories ---------------------------------


def trajectory_rows():
    from impots import trajectoires as tj

    return tuple(
        tj.year_uncertainty(y, basis=basis, frozen_eur=f, aged_eur=a,
                            base_year=2026, horizon=3)
        for y, basis, f, a in (
            (2026, "legislated", -2.399e9, -2.609e9),
            (2028, "reconducted", -7.073e9, -8.339e9),
            (2030, "reconducted", -11.0e9, -13.4e9)))


def test_a_trajectory_fiche_carries_the_banner_verbatim():
    """The sentence is prescribed word for word by the phase spec, and it is the one
    thing a reader must not have to infer: the population is today's France with
    tomorrow's money. Fails on any rewording."""
    text = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-09", trajectoire=trajectory_rows()))
    assert ("Ce qui est chiffré : ce droit, sur la France d’aujourd’hui, "
            "avec l’argent de demain.") in text


def test_the_per_year_table_names_both_classes_separately():
    """Fails if the two uncertainty classes are merged into one column.

    They answer different questions and on this trajectory the uprating class is the
    larger; a single interval would hide which is doing the work.
    """
    text = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-09", trajectoire=trajectory_rows()))
    assert "| année | base | mécanique | vieillissement" in text
    assert "comportement" in text
    assert "ne sont pas additionnées" in text


def test_the_table_shows_the_frozen_aged_pair_not_just_a_width():
    """M2's ruling: the pair IS the measurement. Showing only «±1,27 Md€» would hide
    which direction ageing moves the figure, and it moves it away from zero."""
    text = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-09", trajectoire=trajectory_rows()))
    assert "-7,07 Md€ → -8,34 Md€" in text


def test_the_band_widens_visibly_with_the_horizon():
    """F3 M5 asks for the widening to be visible. On this trajectory it runs 210 M€ in
    2026 to 2,40 Md€ in 2030 — a fact about the further year being less known, and the
    reason a trajectory is points rather than a curve."""
    text = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-09", trajectoire=trajectory_rows()))
    assert "±210 M€" in text and "±2,40 Md€" in text


def test_a_width_is_unsigned():
    """«±+210 M€» reads as a typo because it is one: the ± already carries the
    two-sidedness. Fails if the signed formatter comes back for widths."""
    assert fiche._width(210e6) == "210 M€"
    assert fiche._width(-1.266e9) == "1,27 Md€"


def test_the_bases_are_named_per_year():
    text = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-09", trajectoire=trajectory_rows()))
    assert "| 2026 | legislated |" in text
    assert "| 2028 | reconducted |" in text
    assert "reporte la dernière valeur votée" in text


def test_the_years_that_lost_their_fan_say_why():
    """The horizon refusal binds per year, so the fiche lists the years it dropped and
    the reason — not one blanket sentence for the reform."""
    text = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-09", trajectoire=trajectory_rows()))
    assert "Éventail macro, refusé pour certaines années" in text
    assert "2030 —" in text


def test_a_single_year_fiche_is_unchanged_by_the_trajectory_code():
    """Every existing caller passes no trajectory, and must render exactly as before."""
    text = fiche.render(response(), PROVENANCE)
    assert "4.2.1 bis" not in text
    assert "argent de demain" not in text


def test_the_uprating_hypothesis_rides_on_the_trajectory_fiche():
    """The ageing indices are a declared hypothesis, so they travel with the figures."""
    from impots.uprating import Uprating

    hypo = Uprating(wage=0.025, price=0.02, source="2,5 % / 2 % ronds", base_year=2024)
    text = fiche.render(response(), fiche.Provenance(
        titre="X", source="s", date="2026-09-09",
        trajectoire=trajectory_rows(), uprating=hypo))
    assert "2,5 % / 2 % ronds" in text
    assert "n'est plus calibrée" in text
