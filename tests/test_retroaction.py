"""Phase 9 M3 — the GDP → receipts loop (`predictif.retroaction`, PHASE9_SPEC §4, D-218).

Most tests run on a CONSTRUCTED macro store, whose tables carry the published Mésange
values the M0 reading pinned (D-214): the arithmetic must hold whatever file is on disk,
and the shipped row has its own tests, which need the PDF.
"""

from __future__ import annotations

import dataclasses

import pytest

from impots.behavioural.store import Source, Support, Verifier
from impots.macro import mesange
from impots.macro.fan import FanError
from impots.macro.store import Store, TableParameter
from impots.predictif import retroaction
from impots.predictif.retroaction import FeedbackError
from impots.predictif.theta import ThetaError

H = mesange.HORIZONS
YEARS = list(range(2026, 2036))
GDP = {y: 3_000e9 * 1.03 ** (y - 2025) for y in YEARS}


def _table(key: str, values: dict, horizons=H, usable=("1", "2", "3")) -> TableParameter:
    return TableParameter(key=key, values=values, horizons=horizons, usable_horizons=usable,
                          applies_to="test", support=Support(estimated_on="test"),
                          source=Source(citation="test"),
                          verifier=Verifier(verdict="CONFIRMED", date="2026-10-19"))


def _store(**balance_overrides) -> Store:
    """IR, CSG and VAT as Mésange prints them (expansionary convention), and the targeted
    variant without a balance row."""
    gdp = {"impot_sur_le_revenu": (0.41, 0.83, 0.88, 0.81, 0.87, 1.05),
           "csg": (0.41, 0.84, 0.90, 0.81, 0.80, 0.88),
           "tva": (0.32, 0.66, 0.72, 0.81, 0.78, 0.70),
           "cotisations_employeurs_ciblees": (0.21, 0.58, 0.80, 1.05, 1.43, 1.84)}
    balance = {"impot_sur_le_revenu": (-0.81, -0.50, -0.42, -0.51, -0.50, -0.43),
               "csg": (-0.81, -0.50, -0.43, -0.52, -0.54, -0.51),
               "tva": (-0.80, -0.36, -0.28, -0.37, -0.44, -0.47), **balance_overrides}
    return Store(tables={
        "multiplier_by_instrument": _table("multiplier_by_instrument", gdp),
        retroaction.BALANCE_TABLE: _table(retroaction.BALANCE_TABLE, balance),
        "multiplier_dispersion": _table("multiplier_dispersion", {"TAX": (0.66,)},
                                        horizons=("all",), usable=("all",)),
    })


def _cut(eur: float, instrument: str = "impot_sur_le_revenu", years=YEARS) -> dict:
    """A permanent cut held at a constant share of GDP: EXPANSIONARY-POSITIVE euros."""
    return {y: {instrument: eur * GDP[y] / GDP[years[0]]} for y in years}


def _run(impulses, years=None, **kwargs):
    """The years are the impulse's unless a test says otherwise."""
    options = {"store": _store(), "theta": 0.5, "persistence": "tenu",
               "spending_rule": "gele_en_volume", **kwargs}
    return retroaction.compute(impulses, GDP, years or sorted(impulses), **options)


# --------------------------------------------------------------------------- #
# the arithmetic, against the pinned reading
# --------------------------------------------------------------------------- #
def test_a_one_point_income_tax_cut_gives_back_what_m0_pinned() -> None:
    """One point of GDP of IR cut: the balance improves by 0,19, 0,50 and 0,58 point of
    GDP at one, two and three years (D-214), and GDP rises by 0,41, 0,83, 0,88 %."""
    one_point = GDP[2026] / 100.0
    result = _run(_cut(one_point, years=YEARS[:3]))
    assert result.balance == pytest.approx((0.0019, 0.0050, 0.0058), abs=1e-12)
    assert result.gdp_gap == pytest.approx((0.0041, 0.0083, 0.0088), abs=1e-12)


def test_vat_is_measured_against_the_gross_cost_the_chain_counts() -> None:
    """The VAT variant costs 1,18 points gross for one net, and the chain's mechanical
    line is the gross cost. Against it, what comes back is solde + 1,18 = 0,38 point per
    variant, the State's own VAT included — not solde + 1 = 0,20, the first draft's
    figure, which the adversarial pass caught (D-218). The GDP effect is divided by 1,18
    as the fan divides it."""
    gross = 1.18 * GDP[2026] / 100.0
    result = _run(_cut(gross, "tva", years=YEARS[:1]))
    assert result.balance[0] == pytest.approx((-0.80 + 1.18) / 100.0, abs=1e-12)
    assert result.gdp_gap[0] == pytest.approx(0.32 / 100.0, abs=1e-12)


def test_a_tax_rise_takes_the_feedback_with_the_opposite_sign() -> None:
    cut = _run(_cut(10e9))
    rise = _run(_cut(-10e9))
    assert rise.balance == pytest.approx(tuple(-b for b in cut.balance))
    assert rise.gdp_gap == pytest.approx(tuple(-g for g in cut.gdp_gap))


def test_a_varying_impulse_is_a_sum_of_permanent_shocks() -> None:
    """Linear model: a cut that doubles in its second year is a first shock plus a
    second one started a year later, each read at its own horizon."""
    one = GDP[2026] / 100.0
    step = {2026: {"impot_sur_le_revenu": one},
            2027: {"impot_sur_le_revenu": 2 * one * GDP[2027] / GDP[2026]},
            2028: {"impot_sur_le_revenu": 2 * one * GDP[2028] / GDP[2026]}}
    result = _run(step, years=YEARS[:3])
    assert result.balance == pytest.approx(
        (0.0019, 0.0050 + 0.0019, 0.0058 + 0.0050), abs=1e-12)


def test_theta_moves_the_multiplier_by_one_sd_and_the_feedback_with_it() -> None:
    one_point = GDP[2026] / 100.0
    low, mid, high = (_run(_cut(one_point, years=YEARS[:1]), theta=t) for t in (0, 0.5, 1))
    assert mid.gdp_gap[0] == pytest.approx(0.0041)
    assert high.gdp_gap[0] == pytest.approx(0.0041 + 0.0066)
    assert low.gdp_gap[0] == pytest.approx(0.0041 - 0.0066)
    # Proportional: the feedback at θ = 1 is 0,19 × 1,07 / 0,41.
    assert high.balance[0] == pytest.approx(0.0019 * 1.07 / 0.41)
    assert low.balance[0] < 0 < mid.balance[0] < high.balance[0]


# --------------------------------------------------------------------------- #
# the four conditions of D-214, each a refusal
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rule", ["part_pib_constante", "personnalise"])
def test_the_loop_is_refused_unless_spending_is_frozen_in_volume(rule: str) -> None:
    with pytest.raises(FeedbackError, match="note 70"):
        _run(_cut(10e9), spending_rule=rule, spending_name="Dépenses en % du PIB")


def test_past_three_years_a_persistence_scenario_is_required() -> None:
    """§4.6: year 4 without a persistence scenario is a named refusal, not year 3 held."""
    with pytest.raises(FeedbackError, match="persistance"):
        _run(_cut(10e9), persistence=None)
    assert len(_run(_cut(10e9, years=YEARS[:3]), persistence=None).years) == 3


def test_the_two_persistence_scenarios_are_what_they_say() -> None:
    one_point = GDP[2026] / 100.0
    held = _run(_cut(one_point), persistence="tenu")
    gone = _run(_cut(one_point), persistence="eteint")
    assert held.balance[3:] == pytest.approx((0.0058,) * 7)
    # Zero to the float: the carried impulse is constant in points of GDP only up to a
    # rounding of 1e-16, so its later « steps » are noise, not shocks.
    assert gone.balance[3:] == pytest.approx((0.0,) * 7, abs=1e-15)
    assert gone.gdp_gap[3:] == pytest.approx((0.0,) * 7, abs=1e-15)
    assert held.balance[:3] == pytest.approx(gone.balance[:3])
    with pytest.raises(FeedbackError, match="inconnue"):
        _run(_cut(one_point), persistence="decroissant")


def test_the_targeted_variant_gets_no_macro_effect_and_says_why() -> None:
    """No balance row: neither feedback nor GDP, rather than half of a variant."""
    mixed = {y: {"impot_sur_le_revenu": 5e9, "cotisations_employeurs_ciblees": 5e9}
             for y in YEARS[:3]}
    result = _run(mixed, years=YEARS[:3])
    alone = _run({y: {"impot_sur_le_revenu": 5e9} for y in YEARS[:3]}, years=YEARS[:3])
    assert result.balance == pytest.approx(alone.balance)
    assert result.gdp_gap == pytest.approx(alone.gdp_gap)
    assert "encadré 14" in result.uncovered["cotisations_employeurs_ciblees"]
    with pytest.raises(FeedbackError, match="aucun instrument"):
        _run({y: {"cotisations_employeurs_ciblees": 5e9} for y in YEARS[:3]},
             years=YEARS[:3])


def test_the_carbon_tax_is_left_out_because_its_gap_is_not_activity() -> None:
    """Its shock falls on energy volumes: the balance gap holds the energy base shrinking,
    which is not an effect of activity (folio 121)."""
    store = _store(taxe_carbone=(-0.68, -0.15, -0.14, -0.24, -0.28, -0.37))
    store.tables["multiplier_by_instrument"].values["taxe_carbone"] = (
        0.51, 0.80, 0.75, 0.87, 0.86, 0.68)
    mixed = {y: {"impot_sur_le_revenu": 5e9, "taxe_carbone": 5e9} for y in YEARS[:3]}
    result = _run(mixed, store=store)
    assert result.instruments == ("impot_sur_le_revenu",)
    assert "énergie" in result.uncovered["taxe_carbone"]


def test_unmapped_deltas_travel_with_their_reasons() -> None:
    result = _run(_cut(10e9), uncovered={"rsa": "transfert : pas de variante"})
    assert result.uncovered == {"rsa": "transfert : pas de variante"}


def test_a_balance_row_read_with_the_wrong_sign_is_refused() -> None:
    """§4.6: the coherence check. Flipped, the IR row reads +0,81 at one year — a cut
    that improves the balance by more than it costs; « solde + 1 » would then add 1,81
    points of GDP nobody measured."""
    flipped = _store(impot_sur_le_revenu=(0.81, 0.50, 0.42, 0.51, 0.50, 0.43))
    with pytest.raises(FeedbackError, match="hors de"):
        _run(_cut(10e9), store=flipped)
    excluded = _store(impot_sur_le_revenu=(0.19, 0.50, 0.58, 0.49, 0.50, 0.57))
    with pytest.raises(FeedbackError, match="hors de"):
        _run(_cut(10e9), store=excluded)


def test_theta_outside_the_unit_interval_and_missing_years_are_refused() -> None:
    with pytest.raises(ThetaError, match="écrêté"):
        _run(_cut(10e9), theta=1.2)
    gap = _cut(10e9)
    del gap[2028]
    with pytest.raises(FeedbackError, match="sans impulsion"):
        _run(gap, years=YEARS)


def test_a_store_without_the_balance_row_is_refused_by_name() -> None:
    store = _store()
    tables = dict(store.tables)
    del tables[retroaction.BALANCE_TABLE]
    with pytest.raises(FanError, match=retroaction.BALANCE_TABLE):
        _run(_cut(10e9), store=dataclasses.replace(store, tables=tables))


# --------------------------------------------------------------------------- #
# the shipped row, read from the PDF (skipped without the primary sources)
# --------------------------------------------------------------------------- #
def _shipped():
    pytest.importorskip("pypdf")
    from impots.macro import imk
    from impots.macro import store as macro_store

    if not ((mesange.RAW / mesange.SOURCE_FILE).exists()
            and (imk.RAW / imk.DOCUMENTS["wp117"]).exists()):
        pytest.skip("data/raw/ has no Mésange or IMK document — primary sources are not "
                    "committed")
    return macro_store.load()


def test_the_shipped_row_gives_back_what_m0_pinned() -> None:
    """D-214's six feedbacks, against the gross cost: one point for the labour taxes and
    the CSG, 1,18 for VAT; the carbon tax is not read."""
    loaded = _shipped()
    pins = {"impot_sur_le_revenu": (0.19, 0.50, 0.58), "csg": (0.19, 0.50, 0.57),
            "cotisations_salaries": (0.27, 0.53, 0.61),
            "cotisations_employeurs": (0.28, 0.58, 0.73),
            "tva": (0.38, 0.82, 0.90)}
    for instrument, pinned in pins.items():
        gross = mesange.VARIANTS[instrument].ex_ante_points
        one = gross * GDP[2026] / 100.0
        result = _run(_cut(one, instrument, years=YEARS[:3]), store=loaded)
        assert result.balance == pytest.approx(tuple(p / 100 for p in pinned), abs=1e-12)
    retroaction.check_balance(loaded.tables[retroaction.BALANCE_TABLE])


def test_the_shipped_row_does_not_load_without_its_verdict(tmp_path) -> None:
    """§4.6: a feedback row with no verifier verdict does not load."""
    import yaml

    from impots.behavioural.store import UnverifiedParameter
    from impots.macro import store as macro_store

    _shipped()
    document = yaml.safe_load(
        (macro_store.PARAMETERS / "multipliers.yaml").read_text(encoding="utf-8"))
    body = document["parameters"][retroaction.BALANCE_TABLE]
    body["verifier"]["verdict"] = None
    (tmp_path / "m.yaml").write_text(yaml.safe_dump(
        {"parameters": {retroaction.BALANCE_TABLE: body},
         "source_table": document["source_table"]}), encoding="utf-8")
    with pytest.raises(UnverifiedParameter, match=retroaction.BALANCE_TABLE):
        macro_store.load(tmp_path)


def test_an_absence_must_be_declared_and_a_declaration_must_be_true() -> None:
    """The targeted variant prints no balance row: declared, it is left out; undeclared,
    the row is refused; declared for a variant that prints it, refused as stale."""
    _shipped()
    values, _ = mesange.table("solde_primaire_pts_pib",
                              absent_for=["cotisations_employeurs_ciblees"])
    assert "cotisations_employeurs_ciblees" not in values and "csg" in values
    with pytest.raises(mesange.MesangeError, match="absent from"):
        mesange.table("solde_primaire_pts_pib")
    with pytest.raises(mesange.MesangeError, match="declared absent"):
        mesange.table("solde_primaire_pts_pib",
                      absent_for=["cotisations_employeurs_ciblees", "csg"])


# --------------------------------------------------------------------------- #
# the impulse, out of what the population layer reports (D-218)
# --------------------------------------------------------------------------- #
#: What `aggregate.deltas` carries for an income-tax rise, receipts-positive: the tax,
#: its components, the totals it moves, and a benefit the RSA cascade nudges.
POPULATION_DELTAS = {"ir": 1.62e9, "ir_avant_niches": 1.70e9, "reductions": 0.08e9,
                     "credits_impot": 0.0, "revenu_disponible": -1.61e9,
                     "salaire_net": 0.0, "rsa": 0.01e9, "crds_mini": -0.00005e9}


def test_the_raw_population_deltas_cannot_build_a_shock() -> None:
    """The defect the real run found: handed whole, the income tax's components and the
    totals make the builder refuse, and every macro path came back unavailable."""
    from impots.macro import shocks

    with pytest.raises(shocks.ShockError, match="ir_avant_niches"):
        shocks.build(POPULATION_DELTAS, year=2026)


def test_the_shock_reads_the_instruments_the_sector_balance_counts() -> None:
    """Receipts as reported, transfers negated into the same convention, the employer
    contributions actually paid — and none of the components, which would double the
    tax."""
    from impots.macro import shocks

    selected = shocks.instrument_deltas(POPULATION_DELTAS,
                                        employer_contribution_delta=-2e9)
    assert set(selected) == {"ir", "rsa", "crds_mini", "employer_contributions"}
    assert selected["rsa"] == -0.01e9 and selected["employer_contributions"] == -2e9
    impulse = shocks.build(selected, year=2026)
    assert impulse.by_instrument == {"impot_sur_le_revenu": -1.62e9,
                                     "cotisations_employeurs": 2e9}
    assert set(impulse.unmapped) == {"rsa", "crds_mini"}
    assert set(impulse.reasons()) == {"rsa", "crds_mini"}


# --------------------------------------------------------------------------- #
# M4 — the corporate tax receives no multiplier (PHASE9_SPEC §5, D-219)
# --------------------------------------------------------------------------- #
def test_a_corporate_tax_delta_receives_no_multiplier_and_no_loop() -> None:
    """§5's kill test. Mésange has no IS variant, and the IS must not borrow the employer
    contributions' multiplier, which runs through the cost of labour: the delta stays
    unmapped with its reason, and a loop made of it alone is absent, not zero."""
    from impots.macro import shocks

    impulse = shocks.build({"impot_societes": 1e9}, year=2026)
    assert impulse.by_instrument == {}
    assert "coût du capital" in impulse.reasons()["impot_societes"]
    with pytest.raises(retroaction.NothingToRead, match="impot_societes"):
        _run({y: {} for y in YEARS[:3]}, years=YEARS[:3], uncovered=impulse.reasons())
