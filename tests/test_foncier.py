"""F5 M1 — the taxe foncière cells.

The load-bearing test is the identity: this is the first module in the project whose cells
are PUBLISHED rather than constructed, so the baseline check is «does our arithmetic on
their bases reproduce their produits» — a far stronger question than «does our synthetic
population reproduce a total», and one with a far cleaner answer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from impots.foncier import cells as fc
from impots.foncier import knobs as fk

ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "raw" / "rei_2025.zip"
needs_rei = pytest.mark.skipif(not ARCHIVE.exists(), reason="REI non téléchargé")


@pytest.fixture(scope="module")
def cells():
    if not ARCHIVE.exists():
        pytest.skip("REI non téléchargé")
    return fc.read()


@needs_rei
def test_every_commune_is_read_and_none_is_synthesised(cells):
    """No imputation, no draw, no cell fitted to a total — the first module in this
    project of which that is true. Fails if a row count drifts from the published one."""
    assert cells.communes == 34_907
    assert "commune" in cells.strata and "intercommunalite" in cells.strata


@needs_rei
def test_the_identity_holds_to_rounding(cells):
    """base × taux / 100 + lissage = produit, commune by commune.

    Measured: median 0,006 %, 99th percentile 0,41 %. Fails if the arithmetic drifts, if
    the rates stop being read as percentages, or if the lissage term is dropped.
    """
    residuals = fc.identity_residuals(cells)
    assert residuals.height > 34_000
    assert residuals["residual"].median() < 1e-4
    assert residuals["residual"].quantile(0.99) < 0.005


@needs_rei
def test_the_lissage_is_part_of_the_identity_not_a_correction(cells):
    """THE term a two-factor reading omits.

    13 430 communes carry a non-zero lissage, and including it moves the national total
    and tightens their residual by more than an order of magnitude. Fails if it is
    dropped — the result would still look plausible, which is why it is tested rather
    than trusted.
    """
    import polars as pl

    frame = cells.frame
    assert "fb_commune_lissage" in frame.columns
    with_lissage = frame.filter(pl.col("fb_commune_lissage") != 0).height
    assert with_lissage > 10_000, "le lissage doit concerner un grand nombre de communes"

    # Without the term, the same communes reconcile an order of magnitude worse.
    both = (frame
            .filter((pl.col("fb_commune_lissage") != 0) & (pl.col("fb_commune_base") > 0)
                    & (pl.col("fb_commune_produit") > 0))
            .with_columns(
                sans=((pl.col("fb_commune_base") * pl.col("fb_commune_taux") / 100.0
                       - pl.col("fb_commune_produit")) / pl.col("fb_commune_produit")).abs(),
                avec=((pl.col("fb_commune_base") * pl.col("fb_commune_taux") / 100.0
                       + pl.col("fb_commune_lissage") - pl.col("fb_commune_produit"))
                      / pl.col("fb_commune_produit")).abs()))
    assert both["avec"].median() < both["sans"].median() / 5


@needs_rei
def test_the_unreconciled_communes_are_pinned_not_absorbed(cells):
    """55 communes stay more than 1 % out even with the lissage, every one of them with
    NO lissage — so the term is not what is missing. Their effective rate sits below
    their published rate, which points at an abattement this module does not read.

    Pinned as a count. A residual with a name is a lead; a residual absorbed into a
    tolerance is a lie with error bars. Fails if the count moves — in either direction,
    because an improvement is a finding too and deserves its D-entry.
    """
    residuals = fc.identity_residuals(cells)
    out = int((residuals["residual"] > fc.IDENTITY_TOLERANCE).sum())
    assert out == fc.UNEXPLAINED_COMMUNES == 55


@needs_rei
def test_the_national_total_matches_the_gate(cells):
    """43,49 md€ across the strata, against the 43,1 md€ the DGFiP publishes hors taxes
    annexes — the +0,9 % of D-100, now reproduced through the cells rather than an
    ad-hoc script."""
    total = fc.national(cells)
    assert total / 43.1e9 - 1 == pytest.approx(0.009, abs=0.004)


def test_a_missing_stratum_is_refused_rather_than_returned_as_zero():
    """A stratum absent from the cells must raise, not return 0.0 — a silent zero would
    read as «this stratum raises nothing»."""
    empty = fc.Cells(frame=None, vintage="x", strata=())
    with pytest.raises(fc.CellError, match="absente"):
        fc.produit_of(empty, "commune")


@needs_rei
def test_a_stratum_without_a_published_produit_cannot_be_verified(cells):
    """TASA publishes rates and bases but no produit. Checking the identity there is
    impossible, and checking it somewhere else says nothing about it — so it refuses."""
    with pytest.raises(fc.CellError, match="ne publie pas de produit"):
        fc.identity_residuals(cells, "tasa")


# --- M2: the knobs -------------------------------------------------------------------


@needs_rei
def test_the_three_levers_price_on_published_cells(cells):
    """Measured, and the ORDER matters because the intuition is wrong.

    A +3,2 % revalorisation is worth +1,285 md€; a +1 point national rate change is worth
    +1,080 md€. So one POINT of revalorisation (+0,40 md€) is worth LESS than one point of
    rate — a point of revalorisation is 1 % of base, a point of rate is a point on an
    average near 20 %, i.e. a 5 % relative rise. The first draft of the module docstring
    asserted the opposite from intuition; this test pins the arithmetic that corrected it.
    """
    reval = fk.price(cells, fk.FoncierReform(revalorisation=1.032))["delta_eur"]
    one_pt_reval = fk.price(cells, fk.FoncierReform(revalorisation=1.01))["delta_eur"]
    rate = fk.price(cells, fk.FoncierReform(taux_delta_points=1.0))["delta_eur"]
    assert reval == pytest.approx(1.285e9, rel=0.02)
    assert rate == pytest.approx(1.080e9, rel=0.02)
    assert one_pt_reval < rate, "un point de revalorisation vaut MOINS qu'un point de taux"


@needs_rei
def test_a_commune_set_restricts_the_rate_change(cells):
    """Paris is one commune (75056), not twenty arrondissements — and it alone is worth
    about 90 M€ per rate point, some 8 % of the national point."""
    out = fk.price_checked(cells, fk.FoncierReform(taux_delta_points=1.0,
                                                   communes=("75056",)))
    assert out["communes_touchees"] == 1
    assert out["delta_eur"] == pytest.approx(0.0898e9, rel=0.05)


@needs_rei
def test_a_commune_set_that_matches_nothing_is_refused(cells):
    """THE guard, and it caught its own author: my first Paris test used 75101-75120,
    which are arrondissements and match no commune.

    A zero from an empty set reads as «the measure is free» and is indistinguishable from
    a real zero unless somebody counts. Fails if the refusal is removed.
    """
    with pytest.raises(fk.KnobError, match="ne porte sur personne"):
        fk.price_checked(cells, fk.FoncierReform(taux_delta_points=1.0,
                                                 communes=("99999", "88888")))


@needs_rei
def test_the_baseline_is_our_arithmetic_not_their_published_produit(cells):
    """Comparing a reformed figure computed one way against a baseline read another would
    fold the identity's residual into every reform's cost. Small (0,006 % median) but not
    zero, and it has no business inside a chiffrage.

    Fails if `price` starts reading the produit column as its baseline.
    """
    import polars as pl

    out = fk.price(cells, fk.FoncierReform(taux_delta_points=1.0))
    ours = float(cells.frame.select(fc.produit_of(cells, "commune").sum()).item())
    theirs = float(cells.frame.select(pl.col("fb_commune_produit").sum()).item())
    assert out["baseline_eur"] == pytest.approx(ours)
    assert out["baseline_eur"] != pytest.approx(theirs, abs=1.0), (
        "les deux diffèrent, et c'est pour cela que le choix compte")


@pytest.mark.parametrize("kwargs,fragment", [
    ({}, "réforme foncière vide"),
    ({"revalorisation": 3.2}, "MULTIPLICATEUR"),
    ({"taux_delta_points": 900.0}, "fraction passée pour des points"),
    ({"revalorisation": 1.02, "communes": ("75056",)}, "changement de TAUX"),
])
def test_a_reform_that_would_mislead_is_refused(kwargs, fragment):
    """Unit traps, each with its own message: a revalorisation of 3,2 (not 1,032) and a
    rate delta of 900 points are both a factor confusion, and restricting a NATIONAL
    revalorisation to a commune set is a category error."""
    with pytest.raises(fk.KnobError, match=fragment):
        fk.FoncierReform(**kwargs)


def test_the_revalorisation_names_the_rule_it_changes():
    """It is not a rate anyone votes: since the LF 2017 the coefficient is read off the
    IPCH. Changing it is a change to an indexation RULE, and the knob says so."""
    assert "1518 bis" in fk.REVALORISATION_REFERENCE
    assert "IPCH" in fk.REVALORISATION_REFERENCE


# --- M3: the reconciliation, and the household figure that cannot exist ---------------


@needs_rei
def test_the_national_line_lands_inside_its_declared_tolerance(cells):
    """+0,90 % against the 43,1 md€ published hors taxes annexes."""
    from impots.foncier import reconcile as fr

    line = next(ln for ln in fr.lines(cells) if "produit national" in ln.label)
    assert line.status == "within tolerance"
    assert line.residual == pytest.approx(0.009, abs=0.004)


@needs_rei
def test_the_line_states_the_circularity(cells):
    """The publication is derived from the same REI, so the line validates our READING
    and not a model. Fails if that sentence goes — it is the difference between an audit
    and a claim."""
    from impots.foncier import reconcile as fr

    line = next(ln for ln in fr.lines(cells) if "produit national" in ln.label)
    assert "CIRCULAIRE" in line.note
    assert "43,1" in line.source and "55,1" in line.source, (
        "le comparateur ET le mauvais comparateur doivent tous deux être nommés")


@needs_rei
def test_the_identity_is_an_audit_not_a_reconciliation_line(cells):
    """A Line compares a simulated figure to a published TARGET; the identity compares a
    computed figure to the same source's own figure with a target of zero error. Forcing
    it into the Line shape was a category error, and it broke `Line.status` — which is
    how the category error was found."""
    from impots.foncier import reconcile as fr

    audit = fr.identity_audit(cells)
    assert audit["communes"] > 34_000
    assert audit["median_relative_error"] < 1e-4
    assert audit["unexplained"] == 55
    assert "IDENTITÉ" in audit["note"]
    assert all("Identité" not in ln.label for ln in fr.lines(cells))


def test_a_line_with_a_zero_target_refuses_rather_than_crashes():
    """`residual` is None when `published == 0`, and `status` used to assert it away —
    so any line legitimately targeting zero raised an AssertionError.

    A relative residual against zero is not a large number, it is not a number: the same
    reasoning the chiffrage harness applies. Fails if the assert comes back.
    """
    from impots.reporting import Line

    line = Line(label="x", simulated=5.0, published=0.0, unit="EUR", source="s",
                use="validation", tolerance=0.1)
    assert line.status == "not comparable (cible nulle)"
    assert line.passes is False


def test_there_is_no_per_household_taxe_fonciere_and_the_refusal_says_why():
    """THE limit of this module, and it is permanent rather than pending.

    A household's TF is its property's valeur locative times its commune's rates. The
    rates are published; the valeur locative of an individual property is not, by any
    open source. Showing the commune's rate beside a household's other figures would read
    as an estimate of their tax to every user who saw it.

    Fails if the refusal is softened into a caveat.
    """
    from impots.foncier import reconcile as fr

    text = fr.household_refusal()
    assert "ne peut pas calculer VOTRE taxe foncière" in text
    assert "pas une limite temporaire" in text
    assert "valeur locative" in text
