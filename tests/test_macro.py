"""M0 — the input-output reconnaissance gate, and the kill tests for its assertions.

The gate itself is `scripts/verify_tes.py`. It is exercised here so CI runs it, and
each of its checks is watched failing on a doctored table: a gate nobody has seen fail
is not a gate. Phase 3 shipped a double-entry guard that self-balanced and passed the
exact bug it was written for, which is why this file exists in this shape.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from impots.macro import tes

pytest.importorskip("openpyxl")

ROOT = Path(__file__).resolve().parents[1]
VINTAGES = ("2023SD", "2022DEF")
HAVE_TES = all((tes.RAW / f"insee_TES_symetrique_A38_{v}.xlsx").exists() for v in VINTAGES)
HAVE_JOBS = (tes.RAW / tes.EMPLOYMENT_FILE).exists()
needs_tes = pytest.mark.skipif(
    not (HAVE_TES and HAVE_JOBS),
    reason="data/raw/ has no INSEE input-output tables — they are not redistributable",
)


def _gate():
    spec = importlib.util.spec_from_file_location("verify_tes", ROOT / "scripts" / "verify_tes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_tes"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return _gate()


@pytest.fixture(scope="module")
def table():
    return tes.load("2023SD")


@pytest.fixture(scope="module")
def jobs(table):
    return tes.employment(table.branches, year=table.base_year)


@needs_tes
@pytest.mark.parametrize("vintage", VINTAGES)
def test_gate_passes_on_both_published_vintages(gate, vintage):
    """The M0 gate itself. No propagation code may exist while this is red."""
    assert gate.main(vintage) == 0


@needs_tes
def test_the_two_totals_are_not_the_same_column(table):
    """"Total des emplois" is a prefix of "Total des emplois finals".

    A prefix match made both read 3245.8 bn and the balance identity closed anyway,
    because it was then comparing a column against itself.
    """
    finals = table.final_uses["total_emplois_finals"].sum()
    total = table.final_uses["total_emplois"].sum()
    assert total > finals
    assert total == pytest.approx(finals + table.domestic.sum(), abs=1.0)


@needs_tes
def test_base_year_comes_from_the_vintage_not_the_clock(table):
    assert table.base_year == 2023
    assert tes.load("2022DEF").base_year == 2022


@needs_tes
def test_employment_year_actually_selects_a_year(table):
    """The year headers are strings, so an `isinstance(..., int)` filter read nothing."""
    assert tes.employment(table.branches, 2023).sum() != pytest.approx(
        tes.employment(table.branches, 2022).sum()
    )


@needs_tes
def test_hierarchical_employment_rows_are_aliased_not_dropped(table, jobs):
    """Three branches are published under their A17 parent code (CA, CD, CL)."""
    assert len(jobs) == table.n
    for tes_code, published_as in tes.EMPLOYMENT_ALIASES.items():
        index = list(table.branches).index(tes_code)
        assert jobs[index] > 0, f"{tes_code} (published as {published_as}) lost"


@needs_tes
def test_final_consumption_is_the_total_not_the_households_column(table):
    """Four columns sit under one merged "Dépenses de consommation finale" header.

    Matching the header alone takes its leftmost column — Ménages — and the aggregate
    balance identity stays green throughout, because that identity uses a different
    published column. 1 158.7 bn instead of 1 888.2 bn, for as long as nobody added the
    parts up.
    """
    fu = table.final_uses
    assert fu["consommation_finale"].sum() > fu["consommation_finale_menages"].sum()
    assert fu["consommation_finale"].sum() == pytest.approx(
        sum(fu[f"consommation_finale_{s}"].sum() for s in ("menages", "apu", "isblsm")),
        abs=1.0,
    )
    # The institutional split is what a public-spending shock enters through.
    assert fu["consommation_finale_apu"].sum() > 0


@needs_tes
def test_a_missing_sub_column_raises_rather_than_falling_back(table):
    """The fallback that would have hidden the bug must not exist."""
    with pytest.raises(tes.TesError, match="no sub-column"):
        tes._subcolumn(
            tes._sheet(tes.RAW / f"insee_TES_symetrique_A38_{table.vintage}.xlsx",
                       tes.DOMESTIC_SHEET),
            86, "MENAGES_ETRANGERS", "consommation_finale",
        )


@needs_tes
def test_the_published_table_is_not_non_negative(table):
    """The spec asked for a non-negative import matrix. The data says otherwise.

    KZ->LZ carries the SIFIM adjustment in the 2023 semi-definitive vintage. This test
    pins the finding so that if a later vintage drops it, we notice rather than
    quietly relaxing an assertion nobody remembers.
    """
    i, j = list(table.branches).index("KZ"), list(table.branches).index("LZ")
    assert table.domestic[i, j] < 0
    assert table.imported[i, j] < 0
    assert (np.delete(table.domestic.flatten(), i * table.n + j) >= 0).all()


# --- kill tests: each doctored table must turn the gate red -----------------------


def _broken(table, **changes):
    fields = {f.name: getattr(table, f.name) for f in dataclasses.fields(table)}
    for key, value in changes.items():
        fields[key] = value
    return type(table)(**fields)


@needs_tes
@pytest.mark.parametrize(
    "label",
    ["balance", "components", "negatives", "spectral", "multiplier", "imports"],
)
def test_each_assertion_fires_when_broken(gate, table, jobs, label, capsys):
    if label == "components":
        # The real bug, replayed: final consumption as the households column alone.
        # Note the aggregate balance stays satisfied — only the component check fires.
        uses = dict(table.final_uses)
        uses["consommation_finale"] = uses["consommation_finale_menages"]
        broken = _broken(table, final_uses=uses)
    elif label == "balance":
        broken = _broken(table, total_output=table.total_output * 1.01)
    elif label == "negatives":
        scattered = table.imported.copy()
        scattered[:8, 0] = -1.0
        broken = _broken(table, imported=scattered)
    elif label == "spectral":
        # An economy consuming more of itself than it makes: no convergent inverse.
        runaway = table.domestic.copy()
        np.fill_diagonal(runaway, table.total_output * 1.2)
        broken = _broken(table, domestic=runaway)
    elif label == "multiplier":
        # A negative big enough to make a unit of demand shrink total output.
        sunk = table.domestic.copy()
        sunk[:, 0] = -table.total_output[0] * 0.5
        broken = _broken(table, domestic=sunk)
    else:
        # A share above 1 needs the domestic side negative, so this doctors the one
        # cell where it already is; touching only `imported` leaves the balance intact
        # and isolates the share check. Two positive cells can never breach 1, which is
        # what the first version of this kill test tried and failed to do.
        over = table.imported.copy()
        i, j = list(table.branches).index("KZ"), list(table.branches).index("LZ")
        over[i, j] = abs(table.domestic[i, j]) + 30_000.0
        broken = _broken(table, imported=over)

    assert gate.audit(broken, jobs) is False, f"the {label} check did not fire"


@needs_tes
def test_employment_check_fires_on_a_zero_row(gate, table, jobs):
    zeroed = jobs.copy()
    zeroed[3] = 0.0
    assert gate.audit(table, zeroed) is False


@needs_tes
def test_the_gate_is_green_on_the_real_table(gate, table, jobs):
    """The other half of every kill test: it passes what it should pass."""
    assert gate.audit(table, jobs) is True
