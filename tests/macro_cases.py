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


def synthetic_macro_store() -> Store:
    return Store(tables={
        "multiplier_by_instrument": _table("multiplier_by_instrument", {
            "impot_sur_le_revenu": (0.41, 0.83, 0.88, 0.81, 0.87, 1.05),
            "csg": (0.41, 0.84, 0.90, 0.81, 0.80, 0.88),
            "cotisations_employeurs_ciblees": (0.21, 0.58, 0.80, 1.05, 1.43, 1.84)}),
        "primary_balance_by_instrument": _table("primary_balance_by_instrument", {
            "impot_sur_le_revenu": (-0.81, -0.50, -0.42, -0.51, -0.50, -0.43),
            "csg": (-0.81, -0.50, -0.43, -0.52, -0.54, -0.51)}),
        "multiplier_dispersion": _table("multiplier_dispersion", {"TAX": (0.66,)},
                                        horizons=("all",), usable=("all",)),
    })
