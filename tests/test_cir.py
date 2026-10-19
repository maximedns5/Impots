"""The CIR priced on the créance flow — PHASE8_SPEC §2.3.3's gate, resolved (D-222).

What is held here: the GECIR's tableau 04 and the rates are read out of the publication;
the base split rebuilds the published créance or the instrument refuses to exist; the
Voies et Moyens dépense fiscale is read by its own years and shown beside the créance,
never in its place; a rate change re-prices the créance by hand-derived arithmetic; and
the firm endpoint carries the CIR in its own block, outside `reform_cost`, with the
banner that says a créance is not a disbursement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from impots.agregats import cir
from impots.agregats.engine import AggregateError


def _gecir() -> cir.GecirReading:
    pytest.importorskip("pypdf")
    if not (cir.RAW / cir.GECIR_FILE).exists():
        pytest.skip("data/raw/ n'a pas la publication GECIR 2019 — les sources primaires ne "
                    "sont pas versionnées")
    return cir.read_gecir()


# --------------------------------------------------------------------------- #
# Reading the publications
# --------------------------------------------------------------------------- #
def test_tableau_04_and_the_rates_are_the_ones_printed() -> None:
    """Pinned by eye off the 2019 long publication, p. 12: the 21 declarants above 100 M€
    carry 2 100 M€ below it and 1 790 M€ above, the 19 012 others 20 198 M€; the
    research créance is 6 785 M€; « 30 % jusqu'à un seuil de 100 M€, et de 5 %
    au-delà »."""
    reading = _gecir()
    assert reading == cir.GecirReading(
        millesime=2019, rate_low=0.30, rate_high=0.05, threshold_eur=100e6,
        base_low_others_eur=20_198e6, base_low_big_eur=2_100e6, base_high_eur=1_790e6,
        creance_eur=6_785e6, page=12)


def test_the_base_split_rebuilds_the_published_creance() -> None:
    """Derived by hand: 0,30 × 22 298 + 0,05 × 1 790 = 6 689,4 + 89,5 = 6 778,9 M€
    against 6 785 published, −0,09 %."""
    instrument = cir.instrument(_gecir())
    assert instrument.reconstructed_eur == pytest.approx(6_778.9e6)
    assert instrument.check_base_split() == pytest.approx(6_778.9 / 6_785 - 1)


def test_a_base_split_that_misses_the_creance_refuses_to_exist() -> None:
    """GUARD. Forgetting the 19 012 declarants below the threshold leaves a base that
    rebuilds a tenth of the créance: re-pricing on it would be exact arithmetic on a
    wrong base, and the engine refuses."""
    reading = cir.GecirReading(millesime=2019, rate_low=0.30, rate_high=0.05,
                               threshold_eur=100e6, base_low_others_eur=0.0,
                               base_low_big_eur=2_100e6, base_high_eur=1_790e6,
                               creance_eur=6_785e6, page=12)
    with pytest.raises(AggregateError, match="ventilation"):
        cir.instrument(reading)


def test_the_depense_fiscale_is_read_by_its_own_years() -> None:
    """GUARD. The 200302 sheet prints « Modification 2025 » just before its three years:
    read as the first year, it shifts every amount by one column — 8 041 M€ for 2025
    instead of 2026, and no 2026 at all."""
    pytest.importorskip("pypdf")
    if not (cir.RAW / cir.VM_FILE).exists():
        pytest.skip("data/raw/ n'a pas le tome II de Voies et Moyens")
    assert cir.read_depense_fiscale() == {2024: 7_800e6, 2025: 8_068e6, 2026: 8_041e6}
    sheet = ("200302 – Crédit d'impôt en faveur de la recherche Finalité : x Création 1982 "
             "Réalisation Prévision Prévision Modification 2025 2024 2025 2026 Fin du fait "
             "générateur non borné 7 800 8 068 8 041 Fin d'incidence")
    match = cir.DEPENSE_FISCALE.search(sheet)
    assert [match.group(k) for k in (1, 2, 3)] == ["2024", "2025", "2026"]


def test_years_that_do_not_follow_each_other_are_refused(tmp_path: Path,
                                                         monkeypatch) -> None:
    """GUARD. Three years read off the sheet that are not three years in a row are a
    misread column, and the amounts are refused rather than filed under them."""
    (tmp_path / cir.VM_FILE).write_bytes(b"")
    sheet = ("200302 – Crédit d'impôt en faveur de la recherche Finalité : x "
             "Réalisation Prévision Prévision 2025 2024 2026 Fin du fait générateur "
             "non borné 7 800 8 068 8 041 Fin d'incidence")
    monkeypatch.setattr(cir, "_pages", lambda path: (sheet,))
    with pytest.raises(cir.CirError, match="pas trois années de suite"):
        cir.read_depense_fiscale(tmp_path)


def test_a_missing_publication_names_the_manifest(tmp_path: Path) -> None:
    with pytest.raises(cir.CirError, match="impots data fetch"):
        cir.read_gecir(tmp_path)


# --------------------------------------------------------------------------- #
# Re-pricing the créance
# --------------------------------------------------------------------------- #
def test_a_rate_change_reprices_the_creance_by_hand() -> None:
    """Derived by hand: 25 % instead of 30 % below the threshold is −0,05 × 22 298 =
    −1 114,9 M€ of créance; 10 % instead of 5 % above it, +0,05 × 1 790 = +89,5 M€."""
    reading = _gecir()
    assert cir.price(reading, cir_taux=0.25).delta_eur == pytest.approx(-1_114.9e6)
    assert cir.price(reading, cir_taux_au_dela=0.10).delta_eur == pytest.approx(89.5e6)
    both = cir.price(reading, cir_taux=0.25, cir_taux_au_dela=0.10)
    assert both.delta_eur == pytest.approx(-1_114.9e6 + 89.5e6)


# --------------------------------------------------------------------------- #
# The firm endpoint
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from impots.api import main

    with TestClient(main.app) as test_client:
        yield test_client


def test_the_firm_endpoint_carries_the_cir_in_its_own_block(client) -> None:
    """GUARD. The créance of a millésime and the receipts of a year are two objects: the
    CIR has its block, the dépense fiscale sits beside the créance, and `reform_cost`
    does not move. And the block is national, field for field: no cell, no firm — the
    firm response's own guard lists it as such."""
    _gecir()
    if not (cir.RAW / cir.VM_FILE).exists():
        pytest.skip("data/raw/ n'a pas le tome II de Voies et Moyens")
    body = client.post("/entreprises/simulate",
                       json={"reform": {"cir_taux": 0.25}, "year": 2026}).json()
    block = body["cir"]
    assert set(block) == {
        "millesime", "rates", "rates_reform", "creance_publiee_eur", "creance_eur",
        "creance_reform_eur", "delta_creance_eur", "depense_fiscale_eur", "banner",
        "sources"}
    assert block["delta_creance_eur"] == pytest.approx(-1_114.9e6)
    assert block["creance_publiee_eur"] == 6_785e6
    assert block["rates_reform"] == {"cir_taux": 0.25, "cir_taux_au_dela": 0.05}
    assert block["banner"].startswith("CRÉANCE, PAS DÉCAISSEMENT")
    assert set(block["depense_fiscale_eur"]) == {"2024", "2025", "2026"}
    assert body["reform_cost"] == 0.0


def test_a_reform_without_cir_knobs_has_no_cir_block(client) -> None:
    body = client.post("/entreprises/simulate",
                       json={"reform": {"is_taux_normal": 0.26}, "year": 2026}).json()
    assert body["cir"] is None


def test_the_cir_without_its_sources_is_a_named_503(client, monkeypatch,
                                                     tmp_path: Path) -> None:
    monkeypatch.setattr(cir, "RAW", tmp_path)
    response = client.post("/entreprises/simulate",
                           json={"reform": {"cir_taux": 0.25}, "year": 2026})
    assert response.status_code == 503 and cir.GECIR_FILE in response.json()["detail"]


# --------------------------------------------------------------------------- #
# The coverage claim
# --------------------------------------------------------------------------- #
def test_the_cir_is_priced_since_d222_and_not_counted_as_phase_8s() -> None:
    """GUARD. Bucket B with the banner, priced by the two firm knobs — and recorded as
    priced after Phase 8, so that « ce que la phase 8 a ajouté » stays what it added."""
    from impots import instrument_coverage as ic

    row = next(i for i in ic.INVENTORY if i.code == "cir")
    assert row.bucket == "B" and row.added_by == "D-222"
    assert row.prices_with == ("firm:cir_taux", "firm:cir_taux_au_dela")
    assert row not in ic.new_in_phase_8() and row in ic.added_after_phase_8()


# --------------------------------------------------------------------------- #
# C9 — the R&D response, on the IPP's credible range
# --------------------------------------------------------------------------- #
class Reform:
    def __init__(self, **knobs) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True, **_) -> dict:
        return dict(self._knobs)


CIR_CUT = Reform(cir_taux=0.25)


def _fixed(multiplier: float):
    from impots.behavioural import channels
    from impots.behavioural.store import Parameter, Source, Store, Support, Verifier

    return Store(parameters={channels.C9_KEYS[0]: Parameter(
        key=channels.C9_KEYS[0], central=multiplier, low=multiplier, high=multiplier,
        applies_to="test",
        support=Support(estimated_on="test", max_variation_graded_in_support=0.0),
        source=Source(citation="test"), verifier=Verifier(verdict="CONFIRMED"),
        responds_to_knobs=("cir_taux", "cir_taux_au_dela"))})


def test_the_row_is_the_reports_credible_range() -> None:
    """The store against the PDF: the conclusion's « entre 0.8 et 1.4 », centred on its
    middle. A retyped bound, or a sentence the reader stopped finding, fails here."""
    pytest.importorskip("pypdf")
    from impots.behavioural import ipp22
    from impots.behavioural.store import load

    if not (ipp22.RAW / ipp22.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le rapport IPP n° 22")
    assert ipp22.credible_range() == (0.8, 1.4)
    expected = ipp22.convention(*ipp22.credible_range())
    row = load()["rd_cir_multiplier"]
    assert (row.low, row.central, row.high) == (expected.low, expected.central,
                                                expected.high) == (0.8, 1.1, 1.4)


def test_the_margins_split_the_creance_by_marginal_rate() -> None:
    """Derived by hand from tableau 04: 25 % instead of 30 % moves the créance of the
    declarants below the threshold by −0,05 × 20 198 = −1 009,9 M€, credited at the
    margin at 25 %; that of the 21 above it by −0,05 × 2 100 = −105 M€, credited at the
    margin at 5 %."""
    margins = cir.margins(_gecir(), cir_taux=0.25)
    assert margins[0] == pytest.approx((-1_009.9e6, 0.25))
    assert margins[1] == pytest.approx((-105e6, 0.05))


def test_c9_reproduces_the_worked_example() -> None:
    """Derived by hand at m = 1,1: R = m Δc / (1 − m τ) per group —
    1,1 × −1 009,9 / (1 − 0,275) = −1 532,26 M€ and 1,1 × −105 / (1 − 0,055) =
    −122,22 M€ of R&D; the induced créance is 0,25 × −1 532,26 + 0,05 × −122,22 =
    −389,18 M€. Applied to the static Δc alone (m Δc, the draft's formula), the R&D
    would be −1 226,4 M€: a quarter too small."""
    import numpy as np

    from impots.behavioural import channels

    margins = ((-1_009.9e6, 0.25), (-105e6, 0.05))
    result = channels.rd_response(_fixed(1.1), CIR_CUT, cir_margins=margins, draws=1,
                                  rng=np.random.default_rng(0))
    assert result.applies and not result.in_revenue_band
    expected_rd = 1.1 * -1_009.9e6 / (1 - 0.275) + 1.1 * -105e6 / (1 - 0.055)
    assert result.draws[0] == pytest.approx(expected_rd, rel=1e-12)
    assert result.draws[0] == pytest.approx(-1_654.48e6, abs=0.01e6)
    induced = result.diagnostics["induced_creance_eur"]["p50"]
    assert induced == pytest.approx(0.25 * 1.1 * -1_009.9e6 / 0.725
                                    + 0.05 * 1.1 * -105e6 / 0.945, abs=1.0)


def test_c9_refuses_a_rate_where_the_formula_explodes() -> None:
    """GUARD. At m τ ≥ 1 each euro of induced R&D would pay for itself through its own
    créance: the answer would be infinite or of the wrong sign, and is refused."""
    import numpy as np

    from impots.behavioural import channels

    result = channels.rd_response(_fixed(1.4), Reform(cir_taux=0.75),
                                  cir_margins=((1e9, 0.75), (0.0, 0.05)), draws=1,
                                  rng=np.random.default_rng(0))
    assert not result.applies and "m × τ" in result.message


def test_c9_opens_for_the_cir_knobs_only_and_is_never_revenue() -> None:
    """GUARD. The IS and the production taxes are other instruments; and R&D euros are
    not receipts, nor is a créance a year's receipts — the band of a CIR reform stays
    the mechanical figure's, graded illustrative."""
    import numpy as np

    from impots.behavioural import band, channels
    from impots.behavioural.store import load

    store = load()
    for knob in ("is_taux_normal", "cvae_taux_max", "ir_bareme"):
        quiet = channels.rd_response(store, Reform(**{knob: 0.1}),
                                     cir_margins=((1e9, 0.3),), draws=1,
                                     rng=np.random.default_rng(0))
        assert not quiet.applies and quiet.message == channels.NO_CIR_KNOB, knob
    assert [p.key for p in store.for_knob("cir_taux")] == ["rd_cir_multiplier"]
    result = band.compute(mechanical=0.0, reform=CIR_CUT, store=_fixed(1.1),
                          cir_margins=((-1_009.9e6, 0.25), (-105e6, 0.05)), draws=20)
    assert result.band is None and result.grade == "illustrative"


def test_c9_without_its_margins_says_so() -> None:
    from impots.behavioural import channels

    quiet = channels.rd_response(_fixed(1.1), CIR_CUT)
    assert not quiet.applies and quiet.message.startswith("Non calculé")


# --------------------------------------------------------------------------- #
# The trajectory's closed channels
# --------------------------------------------------------------------------- #
def test_the_trajectory_says_why_c8_and_c9_stay_out_of_it() -> None:
    """A closed channel's reason is shown on every trajectory. « aucun fichier GECIR ni
    MESR au manifeste » beside two GECIR publications would be false on its face — and
    « aucune évaluation publiée » has been, beside C8, since D-221. Both channels are open
    on the firm layer; what keeps them out of a trajectory is that they are indices, never
    receipts, and that the chain prices the population's reforms."""
    from impots.predictif import chaine

    for label, code, entry in (("créations d'entreprises", "C8", "D-221"),
                               ("R&D et CIR", "C9", "D-222")):
        reason = chaine.CLOSED[label]
        assert code in reason and entry in reason and "jamais une recette" in reason, label
        assert "au manifeste" not in reason, label
