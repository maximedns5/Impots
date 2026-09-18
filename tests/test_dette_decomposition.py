"""Phase 8 §3.6 — the decomposition display, and the accidental claims it refuses."""

from __future__ import annotations

import pytest

from impots.dette import decomposition as deco
from impots.dette.path import DebtError

YEARS = (2026, 2027, 2028)
CENTRAL = (1.175, 1.19, 1.21)


def _slice(source="bande", *, label="bande comportementale", width=0.01, **kw):
    return deco.Slice(source=source, label=label,
                      low=tuple(c - width for c in CENTRAL),
                      high=tuple(c + width for c in CENTRAL), **kw)


def _deco(*slices, spending="Dépenses constantes en % du PIB"):
    return deco.Decomposition(years=YEARS, central=CENTRAL, slices=slices,
                              spending_name=spending)


# --------------------------------------------------------------------------- #
# the guard that carries the module: an absent slice is never a zero one
# --------------------------------------------------------------------------- #
def test_an_uncomputed_slice_may_not_carry_values() -> None:
    """THE guard. Values on an uncomputed slice would be drawn and the flag lost.

    The implementation that fails this test is the obvious convenience: keeping the
    numbers « just in case » beside `computed=False`. The renderer reads the numbers.
    """
    with pytest.raises(DebtError, match="ne porte RIEN"):
        deco.Slice(source="bande", label="bande", low=(0.0,), high=(0.0,),
                   computed=False, reason="pas de réforme chiffrée")


def test_an_uncomputed_slice_must_say_why() -> None:
    """« non calculé » with no reason is indistinguishable from « nul » to a reader."""
    with pytest.raises(DebtError, match="sans raison"):
        deco.Slice(source="bande", label="bande", computed=False)


def test_the_width_of_an_uncomputed_slice_is_none_not_zero() -> None:
    """None forces every caller to handle absence; 0.0 lets it average in silently.

    The implementation that fails this test: returning 0.0 for convenience, after which
    an unmeasured band plots as a flat line beside three wide ones and reads as
    « le comportement ne déplace pas cette trajectoire ».
    """
    entry = deco.Slice(source="bande", label="bande", computed=False,
                       reason="aucune réforme n'a encore été chiffrée")
    assert entry.width_at(0) is None
    assert _slice().width_at(0) == pytest.approx(0.02)


def test_a_slice_declared_computed_but_empty_is_refused() -> None:
    """Empty-and-computed would render at width zero, which is an assertion."""
    with pytest.raises(DebtError, match="déclarée calculée mais vide"):
        deco.Slice(source="bande", label="bande")


# --------------------------------------------------------------------------- #
# the dominance question, which is the whole point of the display
# --------------------------------------------------------------------------- #
def test_no_dominant_source_is_named_while_any_slice_is_unmeasured() -> None:
    """The refusal that keeps the display honest.

    The missing slice could be the largest. Naming a winner among the others would read
    as a finding about the world rather than an artefact of what happened to be computed.
    """
    d = _deco(_slice("bande", label="bande comportementale", width=0.01),
              deco.Slice(source="eventail", label="éventail macro", computed=False,
                         reason="aucun multiplicateur applicable à cet horizon"))
    with pytest.raises(DebtError, match="non calculée"):
        d.dominant_source(0)
    assert len(d.uncomputed) == 1


def test_the_dominant_source_is_the_widest_once_everything_is_measured() -> None:
    d = _deco(_slice("bande", label="bande comportementale", width=0.005),
              _slice("eventail", label="éventail macro", width=0.02),
              _slice("scenario", label="grille de scénarios", width=0.01))
    assert d.dominant_source(0) == "eventail"


def test_a_mechanical_only_decomposition_has_no_dominant_source() -> None:
    """Rather than returning « mecanique », which would invent an uncertainty."""
    d = _deco(_slice("mecanique", label="trajectoire mécanique", width=0.0))
    with pytest.raises(DebtError, match="aucune tranche d'incertitude"):
        d.dominant_source(0)


# --------------------------------------------------------------------------- #
# no merged envelope, ever
# --------------------------------------------------------------------------- #
def test_the_decomposition_exposes_no_combined_total() -> None:
    """The anti-merge assertion, named so it cannot be « tidied » back in.

    Adding the slices would assert an independence nobody established and destroy the
    only information the display carries. The implementation that fails this test is a
    `total`/`combined`/`envelope` property added for a prettier chart.
    """
    import dataclasses

    # BOTH surfaces. `hasattr` alone misses a dataclass FIELD declared without a
    # default, because such a field is not a class attribute — so `total: tuple[...]`
    # would slip past a hasattr-only check. That hole is the reason this loop reads
    # the field names too.
    names = {f.name for f in dataclasses.fields(deco.Decomposition)}
    for forbidden in ("total", "combined", "envelope", "enveloppe_totale", "band"):
        assert not hasattr(deco.Decomposition, forbidden), (
            f"`{forbidden}` est apparu comme attribut : la fusion des tranches est "
            f"précisément ce que §3.6 refuse")
        assert forbidden not in names, (
            f"`{forbidden}` est apparu comme CHAMP : même refus, et c'est la moitié "
            f"que `hasattr` ne voit pas")


# --------------------------------------------------------------------------- #
# allowlist, labelling, and the scenario name
# --------------------------------------------------------------------------- #
def test_a_source_outside_the_allowlist_is_refused() -> None:
    with pytest.raises(DebtError, match="liste blanche"):
        deco.Slice(source="incertitude_diverse", label="divers",
                   low=(0.0,), high=(1.0,))


def test_two_slices_sharing_a_source_are_refused() -> None:
    with pytest.raises(DebtError, match="partagent une source"):
        _deco(_slice("bande", label="bande A"), _slice("bande", label="bande B"))


def test_a_spending_scenario_claiming_likelihood_is_refused() -> None:
    with pytest.raises(DebtError, match="probabilité"):
        _deco(_slice(), spending="Trajectoire la plus probable")


def test_a_decomposition_without_a_named_spending_scenario_is_refused() -> None:
    with pytest.raises(DebtError, match="scénario de dépense"):
        _deco(_slice(), spending="   ")


def test_an_inverted_envelope_is_refused_rather_than_given_a_negative_width() -> None:
    with pytest.raises(DebtError, match="borne haute sous la borne basse"):
        deco.Slice(source="bande", label="bande", low=(1.0, 1.0), high=(0.9, 1.1))


def test_a_slice_of_the_wrong_length_is_refused() -> None:
    with pytest.raises(DebtError, match="points pour"):
        _deco(deco.Slice(source="bande", label="bande", low=(1.0,), high=(1.1,)))


# --------------------------------------------------------------------------- #
# the rendered display
# --------------------------------------------------------------------------- #
def test_the_display_names_the_scenario_and_carries_the_banner() -> None:
    """§3.5: the name goes ON the chart, not in a tooltip; the banner always rides."""
    lines = _deco(_slice()).lines()
    body = "\n".join(lines)
    assert "Dépenses constantes en % du PIB" in body
    assert "ne sont PAS microsimulées" in body


def test_the_display_says_non_calcule_rather_than_drawing_a_zero() -> None:
    lines = _deco(
        _slice("bande", label="bande comportementale"),
        deco.Slice(source="eventail", label="éventail macro", computed=False,
                   reason="horizon au-delà des multiplicateurs utilisables"),
    ).lines()
    body = "\n".join(lines)
    assert "NON CALCULÉ" in body and "horizon au-delà" in body
    assert "source dominante non désignée" in body
