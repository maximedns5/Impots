"""Phase 11 M2 — the IS on growth, shown beside the debt and never in it (D-246).

What is held here: Gechert and Heimberger's Table 2 is read out of the PDF and the store's
row is that reading per point of cut; the store refuses an international row without its
rank, countries or years, and a lower rank where a higher one is loaded unless an
exception is declared (PHASE11_SPEC §10, guards 1 and 2); and the index `pib_is` is the
ten-year ramp at θ, with its box, absent with its reason when the normal rate does not
move, and outside the debt path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from impots.behavioural import gechert
from impots.behavioural.store import MisrankedRow
from impots.behavioural.store import load as load_store
from impots.predictif import indices
from impots.predictif.theta import Theta

STORE = load_store()
SPEC = indices.KEYS["pib_is"]
YEARS = list(range(2026, 2038))


def _paper() -> gechert.Reading:
    pytest.importorskip("pypdf")
    if not (gechert.RAW / gechert.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le document de travail de l'IMK — les sources "
                    "primaires ne sont pas versionnées")
    return gechert.load()


# --------------------------------------------------------------------------- #
# The paper, and the row
# --------------------------------------------------------------------------- #
def test_table_2_is_read_as_printed() -> None:
    """Pinned by eye off Table 2 (PDF p. 16): the raw unweighted average, then the
    means beyond publication bias. A rise of a point is the paper's direction."""
    reading = _paper()
    assert reading.table_page == 16
    assert reading.beyond_bias["unw_avg"] == gechert.Coefficient(-0.019, 0.010)
    assert reading.beyond_bias["wls_base"] == gechert.Coefficient(0.0001, 0.0004)
    assert reading.beyond_bias["iv"] == gechert.Coefficient(-0.002, 0.012)
    assert reading.n == {"unw_avg": 441, "wls_base": 441, "median": 42, "iv": 441,
                         "pcc": 446}


def test_the_store_row_is_the_table_per_point_of_cut() -> None:
    """The YAML against the PDF: both centres change sign, θ = ½ at their midpoint."""
    expected = gechert.convention(_paper())
    row = STORE["is_croissance_pib"]
    assert (row.low, row.high) == (expected.low, expected.high) == (-0.0001, 0.019)
    assert row.central == pytest.approx(expected.central, abs=1e-12)
    assert row.theta_one == "high"
    assert row.support.max_variation_graded_in_support is None
    assert row.rank is not None and row.rank.level == 3 and row.rank.exception


def test_a_range_upside_down_is_refused() -> None:
    reading = gechert.Reading(
        beyond_bias={"unw_avg": gechert.Coefficient(0.019, 0.01),
                     "wls_base": gechert.Coefficient(-0.0001, 0.0004)},
        n={}, table_page=16)
    with pytest.raises(gechert.GechertError, match="à l'envers"):
        gechert.convention(reading)


def test_without_pypdf_the_paper_is_refused_by_name(tmp_path, monkeypatch) -> None:
    """The environment's refusal: the file is there, the library that reads it is not."""
    import importlib.util

    (tmp_path / gechert.SOURCE_FILE).write_bytes(b"%PDF-1.4")
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *args: None if name == "pypdf" else real(name, *args))
    monkeypatch.setattr(gechert, "_pages", lambda path: ("rien ici",))
    with pytest.raises(gechert.GechertError, match="pypdf est requis"):
        gechert.load(tmp_path)


# --------------------------------------------------------------------------- #
# Guards 1 and 2: the order of sources
# --------------------------------------------------------------------------- #
ROW = """
  {key}:
    value: {{central: 0.5, low: 0.0, high: 1.0, distribution: triangular}}
    theta: {{un: high, raison: plus grand est plus fort}}
    applies_to: une ligne de test
    responds_to_knobs: [is_taux_normal]
    support: {{estimated_on: rien, max_variation_graded_in_support: null}}
    source: {{citation: personne, url: "http://example.invalid"}}
    verifier: {{verdict: CONFIRMED, date: 2026-10-25, ref: test}}
    rang:
{rank}
"""


def _store(tmp_path: Path, *rows: tuple[str, str]) -> Path:
    body = "".join(ROW.format(key=key, rank=rank) for key, rank in rows)
    (tmp_path / "rows.yaml").write_text("parameters:" + body, encoding="utf-8")
    return tmp_path


FULL = ("      niveau: 3\n      canal: test\n      pays: 42 études\n"
        "      annees: 1997-2019\n      pourquoi: aucune estimation française\n")


@pytest.mark.parametrize("rank, needle", [
    ("      niveau: 3\n      canal: test\n      annees: 1997-2019\n"
     "      pourquoi: aucune\n", "sans les pays ou les années"),
    ("      niveau: 2\n      canal: test\n      pays: 17 pays\n"
     "      pourquoi: aucune\n", "sans les pays ou les années"),
    ("      niveau: 3\n      canal: test\n      pays: 42 études\n"
     "      annees: 1997-2019\n", "pourquoi le rang au-dessus manque"),
    ("      niveau: 5\n      canal: test\n", "inconnu"),
    ("      niveau: 3\n      pays: 42 études\n      annees: x\n      pourquoi: y\n",
     "sans canal"),
], ids=["sans-pays", "sans-annees", "sans-pourquoi", "rang-inconnu", "sans-canal"])
def test_an_international_row_without_its_label_is_refused(tmp_path: Path, rank: str,
                                                           needle: str) -> None:
    """Guard 1 of §10: the row says its rank, countries and years, and why the rank
    above is missing — or the exception that sets it aside."""
    with pytest.raises(MisrankedRow, match=needle):
        load_store(_store(tmp_path, ("ligne", rank)))
    assert "ligne" in load_store(_store(tmp_path, ("ligne", rank)), strict=False).rejected


def test_a_full_label_loads(tmp_path: Path) -> None:
    assert "ligne" in load_store(_store(tmp_path, ("ligne", FULL)))


def test_a_lower_rank_beside_a_higher_one_is_refused_unless_excepted(tmp_path: Path) -> None:
    """Guard 2 of §10: one only goes down a rank when the one above is missing."""
    french = "      niveau: 1\n      canal: test\n"
    with pytest.raises(MisrankedRow, match="une ligne de rang 1 est chargée"):
        load_store(_store(tmp_path, ("francaise", french), ("meta", FULL)))
    lenient = load_store(_store(tmp_path, ("francaise", french), ("meta", FULL)),
                         strict=False)
    assert "meta" not in lenient and "meta" in lenient.rejected
    assert "francaise" in lenient
    other = FULL.replace("canal: test", "canal: autre")
    assert "meta" in load_store(_store(tmp_path, ("francaise", french), ("meta", other)))
    excepted = FULL.replace("      pourquoi: aucune estimation française\n",
                            "      exception: D-000 écarte le rang 1\n")
    assert "meta" in load_store(_store(tmp_path, ("francaise", french),
                                       ("meta", excepted)))


# --------------------------------------------------------------------------- #
# The index
# --------------------------------------------------------------------------- #
def _index(theta: float, change: float | None, years=YEARS) -> indices.Index:
    return indices.is_growth(SPEC, theta=Theta(common=theta), store=STORE,
                             rate_change_points=change, years=years)


def test_a_cut_is_a_ramp_at_theta_held_after_ten_years() -> None:
    """One point of cut: θ = 1 gives 0,019 % of GDP a year more, ten years running,
    then the level holds; θ = 0 the corrected centre's −0,0001 a year."""
    top, bottom, middle = _index(1.0, -1.0), _index(0.0, -1.0), _index(0.5, -1.0)
    assert top.values["2026"] == pytest.approx(0.019)
    assert top.values["2030"] == pytest.approx(0.095)
    assert top.values["2035"] == pytest.approx(0.19)
    assert top.values["2037"] == pytest.approx(0.19)
    assert bottom.values["2035"] == pytest.approx(-0.001)
    assert middle.values["2035"] == pytest.approx(0.0945)
    assert middle.box["2035"] == (pytest.approx(-0.001), pytest.approx(0.19))
    assert indices.IS_OUTSIDE_DEBT in middle.conventions
    assert any(c.startswith("International :") for c in middle.conventions)


def test_a_rise_is_a_negative_gap_and_no_change_is_absent_with_its_reason() -> None:
    assert _index(1.0, 2.0).values["2028"] == pytest.approx(-0.019 * 2 * 3)
    for change in (None, 0.0):
        index = _index(0.5, change)
        assert not index.available and index.reason == indices.NO_IS_RATE


def test_the_index_says_why_when_its_row_did_not_load() -> None:
    from impots.behavioural.store import Store

    bare = Store(rejected={indices.IS_ROW: "un refus de test"})
    index = indices.is_growth(SPEC, theta=Theta(common=0.5), store=bare,
                              rate_change_points=-1.0, years=YEARS)
    assert not index.available and "un refus de test" in index.reason


def test_a_paper_missing_or_misread_is_refused(tmp_path, monkeypatch) -> None:
    with pytest.raises(gechert.GechertError, match="introuvable"):
        gechert.load(tmp_path)
    (tmp_path / gechert.SOURCE_FILE).write_bytes(b"%PDF-1.4")
    title = gechert.TABLE_TITLE
    for pages, needle in (
            (("rien ici",), "le document a changé"),
            ((f"{title}\nN 441 441 42 441 446\n",), "introuvable dans le tableau 2"),
            ((f"{title}\nβ0 [mean beyond bias] −0.019 0.0001\n(0.010) (0.0004)\n"
              f"N 441 441\n",), "5 colonnes attendues"),
            ((f"{title}\nβ0 [mean beyond bias] −0.019 0.0001 0.0002 −0.002 0.033\n"
              f"(0.010) (0.0004) (0.001) (0.012) (0.029)\nN 441 441\n",), "effectifs")):
        monkeypatch.setattr(gechert, "_pages", lambda path, pages=pages: pages)
        with pytest.raises(gechert.GechertError, match=needle):
            gechert.load(tmp_path)
