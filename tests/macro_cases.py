"""A constructed macro store, shared by the tests that run the GDP → receipts loop without
the Mésange PDF: income tax and CSG as Mésange prints them (expansionary convention), and
the targeted variant without a balance row."""

from __future__ import annotations

from impots.behavioural.store import Source, Support, Verifier
from impots.macro import mesange
from impots.macro.store import Store, TableParameter


def _table(key: str, values: dict, horizons=mesange.HORIZONS,
           usable=("1", "2", "3")) -> TableParameter:
    return TableParameter(key=key, values=values, horizons=horizons, usable_horizons=usable,
                          applies_to="test", support=Support(estimated_on="test"),
                          source=Source(citation="test"),
                          verifier=Verifier(verdict="CONFIRMED", date="2026-10-19"))


#: The loop's two rows read 5 and 10 years too, as the shipped store does (D-336).
LOOP_HORIZONS = ("1", "2", "3", "5", "10")


def synthetic_macro_store() -> Store:
    return Store(tables={
        "multiplier_by_instrument": _table("multiplier_by_instrument", {
            "impot_sur_le_revenu": (0.41, 0.83, 0.88, 0.81, 0.87, 1.05),
            "csg": (0.41, 0.84, 0.90, 0.81, 0.80, 0.88),
            "cotisations_employeurs_ciblees": (0.21, 0.58, 0.80, 1.05, 1.43, 1.84)},
            usable=LOOP_HORIZONS),
        "primary_balance_by_instrument": _table("primary_balance_by_instrument", {
            "impot_sur_le_revenu": (-0.81, -0.50, -0.42, -0.51, -0.50, -0.43),
            "csg": (-0.81, -0.50, -0.43, -0.52, -0.54, -0.51)}, usable=LOOP_HORIZONS),
        "multiplier_dispersion": _table("multiplier_dispersion", {"TAX": (0.66,)},
                                        horizons=("all",), usable=("all",)),
    })


def index_rows_store() -> Store:
    """The synthetic store plus the jobs row and the three rows of the §7 indices (D-223),
    as Mésange prints them for the income tax and the targeted variant."""
    built = synthetic_macro_store()
    built.tables.update({
        "employment_by_instrument": _table("employment_by_instrument", {
            "impot_sur_le_revenu": (24.0, 109.0, 174.0, 184.0, 181.0, 200.0),
            "cotisations_employeurs_ciblees": (101.0, 282.0, 403.0, 437.0, 429.0, 468.0)}),
        "consumption_by_instrument": _table("consumption_by_instrument", {
            "impot_sur_le_revenu": (0.81, 1.66, 1.9, 2.01, 2.06, 2.27)}),
        "investment_by_instrument": _table("investment_by_instrument", {
            "impot_sur_le_revenu": (0.81, 2.01, 1.98, 1.32, 1.13, 1.25)}),
        "real_income_by_instrument": _table("real_income_by_instrument", {
            "impot_sur_le_revenu": (1.7, 1.82, 1.92, 2.04, 2.06, 2.27)}),
    })
    return built
