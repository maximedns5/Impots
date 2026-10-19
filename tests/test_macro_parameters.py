"""M1 — the macro parameter store, its refusals, and the kill tests for both.

Two things are pinned here that matter more than the values. First, the store refuses
every row that no verifier has passed — which today is all of them, and the suite says
so out loud rather than letting an unverified band look like a verified one. Second,
the multiplier values live in the PDF and not in the YAML, so the test that would catch
a transcription error is the one asserting there is nothing to transcribe.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from impots.behavioural.store import UnverifiedParameter
from impots.macro import mesange, store

pytest.importorskip("pypdf")

HAVE_SOURCE = (mesange.RAW / mesange.SOURCE_FILE).exists()
needs_source = pytest.mark.skipif(
    not HAVE_SOURCE,
    reason="data/raw/ has no Mésange document — primary sources are not committed",
)

VERIFIED = {
    "value": {"central": 1.0, "low": 0.5, "high": 1.5},
    "applies_to": "a row that passed",
    "support": {"estimated_on": "somewhere"},
    "source": {"citation": "a paper"},
    "verifier": {"verdict": "CONFIRMED", "date": "2026-09-03", "ref": "wf_test"},
}


# --- the refusal, and the proof it is not simply refusing everything ---------------


@needs_source
def test_the_store_loads_what_the_pass_cleared_and_nothing_else():
    """Four rows survived the first adversarial pass and the fifth returned WRONG and is
    gone; the balance row joined after its own pass (D-218)."""
    loaded = store.load()
    assert set(loaded.tables) == {
        "multiplier_by_instrument", "employment_by_instrument",
        "multiplier_dispersion", "multiplier_regime_shift",
        "primary_balance_by_instrument",
    }
    assert loaded.parameters == {}, "no scalar row survived"
    assert "revenue_gdp_elasticity" in loaded.removed


@needs_source
def test_nothing_is_merely_rejected_any_more():
    """Every row is either loaded or removed with a reason — none left in limbo."""
    assert store.load(strict=False).rejected == {}


def test_a_verified_row_loads(tmp_path: Path):
    """The other half of the refusal: a passed verdict must actually get through."""
    (tmp_path / "x.yaml").write_text(
        yaml.safe_dump({"parameters": {"ok": VERIFIED}}), encoding="utf-8")
    loaded = store.load(tmp_path)
    assert loaded["ok"].central == 1.0


@pytest.mark.parametrize("verdict", [None, "WRONG", "PENDING", ""])
def test_only_the_two_loadable_verdicts_pass(tmp_path: Path, verdict):
    body = {**VERIFIED, "verifier": {**VERIFIED["verifier"], "verdict": verdict}}
    (tmp_path / "x.yaml").write_text(
        yaml.safe_dump({"parameters": {"ok": body}}), encoding="utf-8")
    with pytest.raises(UnverifiedParameter):
        store.load(tmp_path)


# --- the values are not in the file that declares them -----------------------------


def test_the_multiplier_yaml_contains_no_multipliers():
    """D-026 in the form a test can check: nothing to transcribe, nothing to drift."""
    document = yaml.safe_load(
        (store.PARAMETERS / "multipliers.yaml").read_text(encoding="utf-8"))
    for key, body in document["parameters"].items():
        value = body["value"]
        assert "from_source_table" in value, f"{key} declares a literal value"
        assert not any(isinstance(v, (int, float)) for v in value.values()), key


@needs_source
def test_table_values_are_the_parsed_ones(tmp_path: Path):
    document = yaml.safe_load(
        (store.PARAMETERS / "multipliers.yaml").read_text(encoding="utf-8"))
    body = document["parameters"]["multiplier_by_instrument"]
    body["verifier"] = dict(VERIFIED["verifier"])
    (tmp_path / "m.yaml").write_text(
        yaml.safe_dump({"parameters": {"multiplier_by_instrument": body},
                        "source_table": document["source_table"]}), encoding="utf-8")
    loaded = store.load(tmp_path)
    table = loaded.tables["multiplier_by_instrument"]
    assert table.at("impot_sur_le_revenu", "1") == pytest.approx(0.41)
    published = mesange.load()["investissement_public"].multiplier
    assert table.profile("investissement_public") == published[:3]


@needs_source
def test_the_long_horizons_are_published_but_refused():
    """5, 10 and LT exist in the source and must not reach a reader.

    Two independent reasons that agree: §0 refuses any horizon past three years, and
    §4.4 shows the long columns are set by a specification choice rather than measured
    — employer contributions give 1.73 at LT under wage-setting and 0.25 under a
    Phillips curve, a factor of seven.
    """
    table = store.load().tables["multiplier_by_instrument"]
    assert table.usable_horizons == ("1", "2", "3")
    assert set(table.horizons) > set(table.usable_horizons)
    for horizon in ("5", "10", "LT"):
        with pytest.raises(KeyError, match="published but not usable"):
            table.at("impot_sur_le_revenu", horizon)


@needs_source
def test_the_targeted_variant_is_separate_and_larger():
    """The most exploitable defect the pass found, pinned.

    A low-wage allègement routed to the uniform variant understates employment by 39 %
    at three years, because a uniform cut lands 80 % on qualified workers while one
    between 1 and 1.6 SMIC lands 44 % on unqualified workers, whose labour demand is
    more elastic.
    """
    jobs = store.load().tables["employment_by_instrument"]
    uniform = jobs.at("cotisations_employeurs", "3")
    targeted = jobs.at("cotisations_employeurs_ciblees", "3")
    assert uniform == 290.0 and targeted == 403.0
    assert targeted / uniform == pytest.approx(1.39, abs=0.01)


@needs_source
def test_the_vat_shock_is_not_one_point_of_gdp():
    """1.18 ex ante for 1 point net, because the state pays about 15 % of its own VAT.

    A VAT reform costed gross ex ante — the usual PLF convention — would otherwise get
    a multiplier overstated by 18 %.
    """
    assert mesange.VARIANTS["tva"].ex_ante_points == 1.18
    assert mesange.VARIANTS["impot_sur_le_revenu"].ex_ante_points == 1.0


@needs_source
def test_the_spending_variants_are_not_ex_ante():
    """p101 reserves the ex ante convention for the FISCAL variants only."""
    assert mesange.VARIANTS["investissement_public"].basis == "volume"
    assert mesange.VARIANTS["depense_publique"].basis == "volume"
    assert mesange.VARIANTS["csg"].basis == "ex_ante_fiscal"


@needs_source
def test_the_overlapping_variants_are_declared():
    """depense_publique already contains 8 % public investment; summing double-counts."""
    assert ("investissement_public", "depense_publique") in mesange.NON_ORTHOGONAL


# --- the parse itself --------------------------------------------------------------


@needs_source
def test_all_nine_variants_parse_with_the_published_values():
    variants = mesange.load()
    assert set(variants) == set(mesange.VARIANTS)
    # Spot values read off the published tables, pinned so a re-parse cannot drift.
    assert variants["investissement_public"].multiplier[:3] == (1.31, 1.38, 1.22)
    assert variants["cotisations_employeurs_ciblees"].multiplier[:3] == (0.21, 0.58, 0.80)
    assert variants["cotisations_employeurs"].jobs[:3] == (83.0, 210.0, 290.0)
    assert variants["depense_publique"].at("gdp", "LT") == pytest.approx(0.16)


@needs_source
def test_the_sign_convention_reverses_the_whole_shock_not_part_of_it():
    """A VAT cut raises GDP *and* costs the budget; both, or the row is incoherent."""
    tva = mesange.load()["tva"]
    assert tva.published_sign == -1
    assert tva.multiplier[0] > 0, "a VAT cut must raise GDP in the expansionary convention"
    assert tva.rows["solde_primaire_pts_pib"][0] < 0, "and must cost the primary balance"
    assert tva.jobs[0] > 0


@needs_source
def test_an_instrument_without_a_published_variant_raises(tmp_path: Path):
    """It must not borrow a neighbour's multiplier."""
    document = yaml.safe_load(
        (store.PARAMETERS / "multipliers.yaml").read_text(encoding="utf-8"))
    body = document["parameters"]["multiplier_by_instrument"]
    body["verifier"] = dict(VERIFIED["verifier"])
    (tmp_path / "m.yaml").write_text(
        yaml.safe_dump({"parameters": {"multiplier_by_instrument": body},
                        "source_table": document["source_table"]}), encoding="utf-8")
    table = store.load(tmp_path).tables["multiplier_by_instrument"]
    with pytest.raises(KeyError, match="impot_societes"):
        table.at("impot_societes", "1")


@needs_source
def test_a_revised_document_raises_rather_than_guessing(monkeypatch):
    """Kill test: if INSEE reprints the variant, the parser must stop, not approximate."""
    monkeypatch.setitem(mesange.VARIANTS, "tva", mesange.VariantSpec(
        "Hausse de la TVA de 2 % du PIB", -1, "ex_ante_fiscal"))
    with pytest.raises(mesange.MesangeError, match="not found"):
        mesange.load()


@needs_source
def test_a_row_with_the_wrong_column_count_raises(monkeypatch):
    """Kill test: a table whose horizons changed must not be read as if they had not."""
    monkeypatch.setattr(mesange, "HORIZONS", ("1", "2", "3", "5", "10", "LT", "extra"))
    with pytest.raises(mesange.MesangeError, match="expected 7"):
        mesange.load()


def test_an_absent_source_file_kills_the_row_loudly(tmp_path: Path):
    with pytest.raises(mesange.MesangeError, match="not found"):
        mesange.load(raw=tmp_path)


# --- dead rows are visible, with reasons -------------------------------------------


@pytest.mark.parametrize("key", [
    "multiplier_slack_state",
    "multiplier_confidence_band",
    "multiplier_impot_societes",
    "revenue_elasticity_by_cycle_state",
    "revenue_gdp_elasticity",
    "mpc_by_income_position",
])
def test_every_dead_row_says_why(key):
    """A channel that shrinks must show why — not merely have fewer inputs."""
    reason = store.load(strict=False).why_removed(key)
    assert len(reason) > 200, f"{key} was removed without a real reason"


@needs_source
def test_the_width_is_the_standard_deviation_not_a_ratio_of_means():
    """The sd is what the source measures; the cv was an artefact of a varying mean.

    Across the eight impulse families the sd spans 0.43-0.89 while the means span a
    factor of four, so a coefficient of variation mostly reports the inverse of the
    mean. This test pins the flatness that makes the absolute width the defensible one.
    """
    from impots.macro import imk

    stats = imk.load("wp117")
    families = ["TRANS", "TAX", "DEFICIT", "SPEND", "CONS", "INVEST", "MILIT", "EMPLOY"]
    sds = [stats[f].sd for f in families]
    means = [stats[f].mean for f in families]
    assert max(sds) / min(sds) < 2.5, "the sd is nearly flat across families"
    assert max(means) / min(means) > 3.0, "the means are not"


@needs_source
def test_the_regime_effect_is_additive_and_the_upturn_is_not_significant():
    """The controlled result, which the raw subsample ratio contradicts.

    The paper's finding is that a downturn ADDS about 0.6-0.8 units to a spending
    multiplier. There is no measured upswing effect to divide by: RUP prints
    -0.049 (0.097) with no stars.
    """
    from impots.macro import imk

    effect = imk.regime_effect()
    assert effect["RLO"].coefficient == pytest.approx(0.769)
    assert effect["RLO"].stars == 3 and effect["RLO"].significant
    assert effect["RUP"].stars == 0 and not effect["RUP"].significant


@needs_source
def test_the_banner_factor_is_not_derivable_and_must_not_be_claimed():
    """D-054 claimed the L4 banner's "facteur 3 à 5" was a measurement. It is not.

    3.5 is a ratio of raw subsample means that the same paper's controlled estimate
    contradicts, and nothing anywhere yields 5. This test exists so the claim cannot
    quietly return.
    """
    from impots.macro import imk

    text = (store.PARAMETERS / "dispersion.yaml").read_text(encoding="utf-8")
    assert "N'EST PAS UNE MESURE" in text
    raw_ratio = imk.load("wp139")["RLO"].mean / imk.load("wp139")["RUP"].mean
    controlled = imk.regime_effect()
    assert raw_ratio > 3.0
    # The controlled coefficients cannot reproduce it, which is the whole point.
    assert controlled["RLO"].coefficient < 1.0


@needs_source
def test_a_statistic_the_tables_do_not_carry_raises():
    from impots.macro import imk

    with pytest.raises(imk.ImkError, match="no statistic"):
        imk.table("skewness", document="wp117")


def test_the_two_seeds_the_spec_supplied_are_both_dead_or_sourced():
    """The spec's 1.3-2.5 slack seed and its MPC row: neither survived M1."""
    reported = store.load(strict=False)
    assert "modèle linéaire" in reported.removed["multiplier_slack_state"]
    assert "PATRIMOINE" in reported.removed["mpc_by_income_position"]


# --- the guard that would have caught the author's own D-026 violations -------------


@needs_source
def test_every_quote_is_verbatim_in_its_source():
    """A `quote:` field must appear WORD FOR WORD in the document it cites.

    Written because the author violated D-026 twice in one sitting, the same way both
    times: a sentence from a search-engine summary set in a `quote:` field as though it
    had been read off the page, and annual figures in a `note:` that the cited document
    never printed. Values were being parsed from primary files while the prose around
    them was not, and nothing checked the prose.
    """
    import re

    import pypdf
    import yaml

    sources = {
        "multipliers.yaml": "insee_G2017-04_mesange.pdf",
        "dispersion.yaml": "imk_wp117_2013_gechert_meta_regression.pdf",
    }
    for name, pdf in sources.items():
        document = yaml.safe_load((store.PARAMETERS / name).read_text(encoding="utf-8"))
        quote = (document.get("source_table") or {}).get("quote", "").strip()
        if not quote:
            continue
        haystack = " ".join(
            " ".join((page.extract_text() or "").split())
            for page in pypdf.PdfReader(mesange.RAW / pdf).pages
        )
        # The extractor hyphenates across line breaks and renders ligatures; compare on
        # letters alone so a real quotation survives and a paraphrase still fails.
        flatten = lambda text: re.sub(r"[^a-zà-ÿ]", "", text.lower())  # noqa: E731
        assert flatten(quote) in flatten(haystack), (
            f"{name}: the quote is not verbatim in {pdf}. Paraphrase is not quotation."
        )
