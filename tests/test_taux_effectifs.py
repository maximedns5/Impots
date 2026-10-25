"""Phase 11 M3 — the OECD's effective tax rates, and the two national indices M3 leaves
closed (D-247).

What is held here: the annex's parameters and the OECD's rates for France are read as
printed; the method gives back buildings, inventories and software within a tenth of a
point, and not the tangibles, whose five subgroups share one published allowance; the
composite EMTR misses M0's condition, so the national entry index is refused, and the
reason the chain gives says so in the computed figures; the investment index stays closed
on what the paper does not print; and an investment or entry index added to the GDP
effect of the IS is refused by name (PHASE11_SPEC §10, guard 7).
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

from impots.entreprises import taux_effectifs as te
from impots.predictif import chaine, indices

RAW = te.RAW


def _files() -> tuple[te.Parameters, dict[str, dict[str, float]]]:
    pytest.importorskip("pypdf")
    for name in (te.ANNEX_FILE, te.PUBLISHED_FILE):
        if not (RAW / name).exists():
            pytest.skip(f"data/raw/ n'a pas {name} — les sources primaires ne sont pas "
                        f"versionnées")
    return te.read_parameters(), te.read_published()


# --------------------------------------------------------------------------- #
# The files, as printed
# --------------------------------------------------------------------------- #
def test_the_annex_and_the_oecd_rates_are_read_as_printed() -> None:
    """Pinned by eye: table A.2's scenario 1, § 8's return, § 18's split, table A.5; the
    OECD's composite for France in 2025, fixed scenario, as M0 read it (D-245)."""
    params, published = _files()
    assert (params.profit, params.real, params.inflation, params.nominal) == (
        0.20, 0.03, 0.01, 0.0403)
    assert params.debt_share == pytest.approx(0.35)
    assert params.depreciation[te.STRUCTURES] == 0.0329
    assert params.depreciation["Computer Hardware"] == 0.3699
    assert params.depreciation[te.SOFTWARE] == 0.4033
    assert published["EMTR"]["COMPOSITE"] == pytest.approx(14.970, abs=5e-4)
    assert published["EATR"]["COMPOSITE"] == pytest.approx(23.613, abs=5e-4)
    assert published["CAPITAL_ALLOWANCES"]["TAN"] == pytest.approx(22.854, abs=5e-4)


def test_the_statutory_rate_is_the_firm_layers() -> None:
    assert te.statutory_rate(2025) == pytest.approx(0.25 * 1.033)


# --------------------------------------------------------------------------- #
# The method
# --------------------------------------------------------------------------- #
PARAMS = te.Parameters(profit=0.20, real=0.03, inflation=0.01, nominal=0.0403,
                       debt_share=0.0, depreciation={})


def test_the_equity_rates_are_the_closed_forms() -> None:
    """Derived by hand from A.1-A.5 and A.8-A.9 with no debt: EATR = (τ(p + δ) − A(r +
    δ))/p, cost of capital = (1 − A)(r + δ)/(1 − τ) − δ."""
    tau, d, a = 0.25825, 0.1259, 0.2
    got = te.rates(d, a, params=PARAMS, tau=tau)
    assert got.eatr == pytest.approx(100 * (tau * (0.2 + d) - a * (0.03 + d)) / 0.2)
    cost = (1 - a) * (0.03 + d) / (1 - tau) - d
    assert got.cost == pytest.approx(100 * cost)
    assert got.emtr == pytest.approx(100 * (cost - 0.03) / 0.03)


def test_debt_lowers_both_rates_and_the_split_weighs_them() -> None:
    tau, d, a = 0.25825, 0.0329, 0.17499
    equity = te.rates(d, a, params=PARAMS, tau=tau)
    debt = te.rates(d, a, params=te.Parameters(**{**PARAMS.__dict__, "debt_share": 1.0}),
                    tau=tau)
    mixed = te.rates(d, a, params=te.Parameters(**{**PARAMS.__dict__, "debt_share": 0.35}),
                     tau=tau)
    assert debt.emtr < equity.emtr and debt.eatr < equity.eatr
    assert mixed.emtr == pytest.approx(0.35 * debt.emtr + 0.65 * equity.emtr)


def test_no_tax_is_no_wedge() -> None:
    assert te.rates(0.1259, 0.0, params=PARAMS, tau=0.0).emtr == pytest.approx(0.0)
    assert te.rates(0.1259, 0.0, params=PARAMS, tau=0.0).eatr == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# The reproduction, and M0's condition
# --------------------------------------------------------------------------- #
def test_three_categories_come_back_and_the_tangibles_do_not() -> None:
    params, published = _files()
    rep = te.reproduce(params, published, te.statutory_rate(2025))
    for category, slack in (("NRS", 0.01), ("INV", 0.01), ("AWS", 0.1)):
        for measure in te.MEASURES:
            assert abs(rep.line(category).gap(measure)) <= slack, (category, measure)
    assert rep.line("TAN").gap("EMTR") == pytest.approx(2.49, abs=0.01)
    assert rep.line("TAN").gap("EATR") == pytest.approx(0.28, abs=0.01)


def test_the_composite_emtr_misses_the_condition_so_the_index_is_refused() -> None:
    """M0, R4: both composites within 0,1 point, or the channel is refused. The EATR comes
    back (23,69 against 23,61); the EMTR does not (15,62 against 14,97)."""
    params, published = _files()
    rep = te.reproduce(params, published, te.statutory_rate(2025))
    assert rep.failures == ("EMTR",) and not rep.passes
    assert rep.line(te.COMPOSITE).gap("EMTR") == pytest.approx(0.646, abs=0.001)
    assert abs(rep.line(te.COMPOSITE).gap("EATR")) < te.TOLERANCE
    assert "TMEI composite 15,62 contre 14,97 publié" in rep.reason()


def test_the_gaps_are_the_ratio_a_varying_allowance_gives() -> None:
    """Whatever the subgroups' allowances, their departure from the average moves the EMTR
    and the EATR in the ratio p/((1 − τ) r): the method is not what fails."""
    params, published = _files()
    observed, expected = te.heterogeneity(
        te.reproduce(params, published, te.statutory_rate(2025)), params)
    assert expected == pytest.approx(8.99, abs=0.01)
    assert observed == pytest.approx(expected, rel=0.02)


def test_a_reproduction_within_tolerance_passes_with_no_reason() -> None:
    line = te.Line(te.COMPOSITE, te.Rates(15.0, 23.6, 3.4), te.Rates(14.97, 23.61, 3.45))
    rep = te.Reproduction(lines=(line,), tau=0.25825)
    assert rep.passes and rep.reason() == ""


# --------------------------------------------------------------------------- #
# The readers' refusals
# --------------------------------------------------------------------------- #
def test_files_missing_are_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(te.EffectiveRateError, match="introuvable"):
        te.read_parameters(tmp_path)
    with pytest.raises(te.EffectiveRateError, match="introuvable"):
        te.read_published(tmp_path)


def test_without_pypdf_the_annex_is_refused_by_name(tmp_path, monkeypatch) -> None:
    (tmp_path / te.ANNEX_FILE).write_bytes(b"%PDF-1.4")
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *args: None if name == "pypdf" else real(name, *args))
    monkeypatch.setattr(te, "_pages", lambda path: ("rien ici",))
    with pytest.raises(te.EffectiveRateError, match="pypdf est requis"):
        te.read_parameters(tmp_path)


SCENARIOS = "Table A.2. Macroeconomic scenarios\n1 (fixed across countries) 1 3 4.03\n"
TEXT = "The pre-tax rate of return is set to 20% throughout. using a 35:65 split\n"
TABLE = ("Table A.5. Economic Depreciation by Asset Category\n"
         "Non-residential Structures 0.0329\n"
         + "".join(f"{g} (Tangible Asset) 0.1000\n" for g in te.TANGIBLES)
         + "Acquired Software 0.4033\n")


@pytest.mark.parametrize("pages, needle", [
    (("rien ici",), "Macroeconomic scenarios"),
    ((SCENARIOS,), "scénario fixe, rendement"),
    ((SCENARIOS + TEXT,), "Economic Depreciation"),
    ((SCENARIOS + TEXT, TABLE.replace("Acquired Software 0.4033\n", "")), "Acquired Software"),
    ((SCENARIOS.replace("4.03", "4.10") + TEXT, TABLE), "Fisher"),
], ids=["sans-tableau-a2", "sans-rendement", "sans-tableau-a5", "sans-logiciels",
        "fisher"])
def test_an_annex_misread_is_refused(tmp_path, monkeypatch, pages, needle) -> None:
    (tmp_path / te.ANNEX_FILE).write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(te, "_pages", lambda path, pages=pages: pages)
    with pytest.raises(te.EffectiveRateError, match=needle):
        te.read_parameters(tmp_path)


def test_a_rate_missing_from_the_oecd_file_is_refused(tmp_path: Path) -> None:
    fields = ["REF_AREA", "TIME_PERIOD", "ETR_SCENARIO", "MEASURE", "ETR_TAX_TYPE",
              "OBS_VALUE"]
    with (tmp_path / te.PUBLISHED_FILE).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow(dict(zip(fields, ["FRA", "2025", "FIXED", "EMTR", "NRS", "7.3"],
                                 strict=True)))
        writer.writerow(dict(zip(fields, ["DEU", "2025", "FIXED", "EMTR", "TAN", "9.0"],
                                 strict=True)))
    with pytest.raises(te.EffectiveRateError, match="EMTR/TAN"):
        te.read_published(tmp_path)


# --------------------------------------------------------------------------- #
# What the chain says, tied to what is computed
# --------------------------------------------------------------------------- #
def test_the_closed_entry_reason_carries_the_computed_refusal() -> None:
    """The reason is static text; this ties it to the computation. If the condition were
    met one day, this fails, and the reason must change with it."""
    params, published = _files()
    rep = te.reproduce(params, published, te.statutory_rate(2025))
    reason = chaine.CLOSED["créations d'entreprises"]
    composite = rep.line(te.COMPOSITE)
    assert not rep.passes
    for figure in (te._fr(composite.computed.emtr), te._fr(composite.published.emtr)):
        assert figure in reason, figure
    for needle in ("Da Rin", "D-247", "sous-groupes", "Ernst & Young", "STAN"):
        assert needle in reason, needle


def _page(name: str, number: int) -> str:
    pytest.importorskip("pypdf")
    if not (RAW / name).exists():
        pytest.skip(f"data/raw/ n'a pas {name}")
    return te._pages(str(RAW / name))[number - 1]


def test_the_authors_construction_is_what_the_reason_says() -> None:
    """Da Rin et al., table 1 (p. 34): their EATR divides by the pre-tax NPV, not by the
    income as the OECD does, and takes its inputs where the reason says."""
    text = _page("da_rin_di_giacomo_sembenelli_2011_aam_firm_entry.pdf", 34)
    # The PDF prints U+2217 for the star and U+2212 for the minus.
    assert "(R\u2217 \u2212 R)/R\u2217" in text
    for source in ("Worldwide", "STAN", "new shares", "12.5%"):
        assert source in text, source


def test_the_investment_index_stays_closed_on_what_is_not_printed() -> None:
    """Hanappi, Millot and Turban: equation (6)'s components sit around reference values
    the annex names and does not print, and figure A E.1 is a picture."""
    import pypdf

    reason = chaine.CLOSED["IS et investissement des entreprises"]
    for needle in ("équation (6)", "valeurs de référence", "figure A E.1", "D-247"):
        assert needle in reason, needle
    name = "hanappi_millot_turban_2023_oecd_eco_wp1765_investment.pdf"
    assert "evaluated at reference values" in _page(name, 61 - 1)
    page = pypdf.PdfReader(str(RAW / name)).pages[60]
    images = [o.get_object() for o in page["/Resources"]["/XObject"].values()]
    assert any(o.get("/Subtype") == "/Image" for o in images)
    text = te._pages(str(RAW / name))[60]
    figure = text.split("Figure A E.1.")[1].split("Note:")[0]
    assert not any(ch.isdigit() for ch in figure.replace("A E.1", ""))


# --------------------------------------------------------------------------- #
# Guard 7: neither enters the GDP
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("other", ["investissement_entreprises", "creations_societes"])
def test_investment_or_entry_added_to_the_gdp_effect_is_refused(other: str) -> None:
    """PHASE11_SPEC §5 and §10, guard 7: the IS's effect on GDP already holds the
    investment and the firms it brings; the sum would count them twice."""
    gdp = indices.Index(spec=indices.KEYS["pib_is"], available=True, values={"2026": 0.1})
    one = indices.Index(spec=indices.KEYS[other], available=True, values={"2026": 1.0})
    for left, right in ((gdp, one), (one, gdp)):
        with pytest.raises(indices.IndicesError, match="compterait deux fois"):
            left + right
