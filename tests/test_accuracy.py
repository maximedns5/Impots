"""Phase 7 A0 — the accuracy budget's kill tests, written before any real case was priced.

The spec's ordering is deliberate and this file is the reason for it: A0's ranking decides
which lever Phase 7 spends its sessions on, so a ranker that cannot be shown to fail would
not produce a wrong number, it would produce a wasted phase.

The governing rule here is D-044's, arrived at five times in this project: **a check
derived from the thing it checks cannot fail when that thing is wrong.** So the synthetic
case's answer is fixed by hand — three spreads in a 100 : 10 : 1 ratio — and never read
back from `budget_for`. And the dominant source is MOVED between tests, because a ranker
that returns a constant order passes any single arrangement.
"""

from __future__ import annotations

import math
import typing

import pytest

from impots import accuracy

# ---------------------------------------------------------------- the kill test itself

@pytest.mark.parametrize("loudest", ["loud", "middle", "quiet"])
def test_the_budget_ranks_the_known_dominant_source_first(loudest: str) -> None:
    """A0's completion condition, and it is parametrized over WHICH source dominates.

    Parametrizing over the answer rather than over the code's own output is the whole
    point: the expected winner is `loudest`, chosen here, and `synthetic_case` is told to
    make that source the loud one. A ranker hard-wired to return the first source, or the
    declaration order, or alphabetical order, fails at least one arrangement.
    """
    sources = accuracy.synthetic_case(dominant=loudest)
    budget = accuracy.budget_for("synthetique", "cas synthétique", 10e9, sources, draws=64)

    dominant = budget.dominant("sampled")
    assert dominant is not None
    assert dominant.source == loudest, (
        f"la source dominante construite est {loudest!r} et le budget classe "
        f"{dominant.source!r} en tête")


@pytest.mark.parametrize("loudest", ["loud", "middle", "quiet"])
def test_the_ranking_recovers_the_full_known_order(loudest: str) -> None:
    """Not just the winner — the whole order, since a lever ranked second still gets built.

    With spreads at 100 : 10 : 1 the variances stand at 10 000 : 100 : 1, so the order is
    unambiguous and hand-checkable.
    """
    sources = accuracy.synthetic_case(dominant=loudest)
    names = [s.key for s in sources]
    rotation = names.index(loudest)
    expected = [names[(rotation + i) % len(names)] for i in range(len(names))]

    ranked = accuracy.budget_for("s", "s", 10e9, sources, draws=96).ranked("sampled")
    assert [c.source for c in ranked] == expected


def test_the_shares_of_one_method_sum_to_one_and_the_loud_one_dominates() -> None:
    """The share is the number a reader acts on, so it gets its own assertion.

    100 : 10 : 1 spreads mean the loud source should carry the overwhelming majority of the
    variance. The threshold is set at 0,95 rather than at the exact 0,9901 the ratio
    implies, because 64 draws of a bounded pseudo-draw carry sampling noise and a test
    pinned to four decimals would be pinning the noise.
    """
    budget = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=96)
    ranked = budget.ranked("sampled")
    assert sum(c.share or 0.0 for c in ranked) == pytest.approx(1.0)
    assert (ranked[0].share or 0.0) > 0.95


# --------------------------------------------------- the refusals, each with its kill

def test_a_sampled_source_without_a_sampler_is_refused() -> None:
    """«sampled» is a claim that a real law exists. Without one it is a bound wearing a
    distribution's clothes, and its variance share would be a convention presented as a
    measurement."""
    with pytest.raises(accuracy.AccuracyError, match="sans échantillonneur"):
        accuracy.Source(key="k", label="l", method="sampled")


def test_a_swing_must_name_both_endpoints() -> None:
    """The endpoints are NAMED because a swing has to say what it is the difference of.

    This is the uprating trap in test form: `(frozen, aged)` is a difference between doing
    the uprating and not doing it, and a source that could not be made to name its
    endpoints could smuggle that in as a low bound.
    """
    with pytest.raises(accuracy.AccuracyError, match="sans fonction ou sans bornes"):
        accuracy.Source(key="k", label="l", method="swing", swing=lambda _n: 0.0)


def test_an_unmeasured_source_must_carry_its_reason() -> None:
    """A source absent from a budget reads as a source that does not matter."""
    with pytest.raises(accuracy.AccuracyError, match="UNMEASURED sans raison"):
        accuracy.Source(key="k", label="l", method="unmeasured")


def test_an_unmeasured_source_is_reported_and_given_no_share() -> None:
    """It must appear, and it must not score. Both halves matter: dropping it hides it,
    scoring it invents a measurement that does not exist."""
    sources = [
        *accuracy.synthetic_case(),
        accuracy.Source(key="cell_bound", label="placement intra-cellule",
                        method="unmeasured",
                        unmeasured_reason="aucune graine seconde n'a jamais été tirée"),
    ]
    budget = accuracy.budget_for("s", "s", 10e9, sources, draws=32)

    unmeasured = budget.unmeasured
    assert [c.source for c in unmeasured] == ["cell_bound"]
    assert unmeasured[0].variance is None
    assert unmeasured[0].share is None
    assert unmeasured[0].note
    # And it did not distort the measured family's shares.
    assert sum(c.share or 0.0 for c in budget.ranked("sampled")) == pytest.approx(1.0)


def test_a_single_draw_is_refused_rather_than_scored_as_zero() -> None:
    """One draw gives variance 0,0, which a ranking reads as «this source does not
    matter» — the exact opposite of what one draw licenses."""
    with pytest.raises(accuracy.AccuracyError, match="un tirage unique"):
        accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=1)


def test_an_empty_source_list_is_refused() -> None:
    with pytest.raises(accuracy.AccuracyError, match="aucune source déclarée"):
        accuracy.budget_for("s", "s", 10e9, [])


# ------------------------------------------- the classes are never mixed, and that is a test

def test_shares_are_computed_within_a_method_and_never_across() -> None:
    """The design's load-bearing refusal.

    A swing's pseudo-variance passes through `VARIANCE_OF_A_RANGE`, an assumed uniform
    shape; a sampled variance passes through no such assumption. Ranking them together
    would rank the conventions. So each family's shares sum to one on their own.
    """
    swing = accuracy.Source(
        key="uprating", label="hypothèse d'uprating", method="swing",
        swing=lambda name: {"bas": 9.0e9, "haut": 11.0e9}[name],
        endpoints=("bas", "haut"),
        note="bornes déclarées par l'appelant, jamais prévues")
    budget = accuracy.budget_for("s", "s", 10e9, [*accuracy.synthetic_case(), swing],
                                 draws=48)

    assert sum(c.share or 0.0 for c in budget.ranked("sampled")) == pytest.approx(1.0)
    assert sum(c.share or 0.0 for c in budget.ranked("swing")) == pytest.approx(1.0)
    assert [c.source for c in budget.ranked("swing")] == ["uprating"]


def test_a_swing_reports_its_width_because_that_needs_no_assumption() -> None:
    """The width is the honest headline for a bounded source: it is what was measured,
    before any shape was assumed over the interval."""
    swing = accuracy.Source(
        key="u", label="u", method="swing",
        swing=lambda name: {"bas": 9.0e9, "haut": 11.0e9}[name], endpoints=("bas", "haut"))
    contribution = accuracy.measure(swing, draws=2, seed=1)

    assert contribution.width_eur == pytest.approx(2.0e9)
    assert contribution.variance == pytest.approx(4.0e18 / accuracy.VARIANCE_OF_A_RANGE)
    assert contribution.sigma_eur == pytest.approx(math.sqrt(4.0e18 / 12.0))


def test_the_range_to_variance_convention_is_a_named_constant() -> None:
    """It is a convention and not a measurement, so it must be arguable in ONE place
    rather than audited across expressions."""
    assert accuracy.VARIANCE_OF_A_RANGE == 12.0


# ------------------------------------------------------------------ determinism

def test_the_same_seed_gives_the_same_budget() -> None:
    """A ranking that moved between runs could not order a phase."""
    a = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=32, seed=7)
    b = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=32, seed=7)
    assert [(c.source, c.variance) for c in a.contributions] == \
           [(c.source, c.variance) for c in b.contributions]


def test_a_different_seed_moves_the_variances_but_not_the_ranking() -> None:
    """The estimate is noisy; the ORDER, at 100 : 10 : 1, must not be.

    If this ever fails, the draw count is too low for the ratio being separated — which is
    a finding about the budget's resolution, not a test to relax.
    """
    a = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=64, seed=11)
    b = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=64, seed=99)
    assert [c.source for c in a.ranked("sampled")] == [c.source for c in b.ranked("sampled")]
    assert a.ranked("sampled")[0].variance != b.ranked("sampled")[0].variance


# --------------------------------------------------- the reference cases (A0's design points)

def test_there_is_exactly_one_reference_reform_per_declared_family() -> None:
    """Eight families, eight cases. Fails if a family is dropped or doubled — a budget
    missing a family reads as a family with no uncertainty."""
    from impots import accuracy_cases

    families = [c.family for c in accuracy_cases.REFERENCE_REFORMS]
    assert len(families) == len(set(families)) == 8, families
    assert set(families) == {"barème", "allègements", "prestations", "niches",
                             "IS", "CVAE", "IFI", "trajectoire"}


def test_a_reference_reform_that_does_not_move_is_refused() -> None:
    """The guard that CVAE's no-op produced.

    `cvae_taux_max = 0,0028` is the value in force, so that case priced at -0,0000 md€ and
    its placement variance was exactly zero — which the report rendered as «placement
    contributes 0,0 % to CVAE», a sentence about a reform that did nothing.
    """
    from impots import accuracy_cases

    noop = accuracy_cases.ReferenceReform(
        key="noop", label="no-op", family="CVAE", chain="firm",
        knob="cvae_taux_max", value=0.0028)
    with pytest.raises(ValueError, match="n'est pas une réforme"):
        accuracy_cases.central_for(noop)


def test_every_cheap_reference_reform_actually_moves() -> None:
    """The positive half: each firm/patrimoine case clears the threshold.

    Both halves are needed. A refusal test alone would pass on a module that refused
    everything, and this project has shipped a denylist-shaped refusal before.
    """
    from impots import accuracy_cases

    for case in accuracy_cases.REFERENCE_REFORMS:
        if case.chain in ("firm", "patrimoine"):
            assert abs(accuracy_cases.central_for(case)) > \
                accuracy_cases.MOVES_EPSILON_EUR, case.key


def test_the_ifi_placement_bound_is_open_because_the_reform_cuts_a_tranche() -> None:
    """At an unchanged barème this bound is a POINT by construction — the patrimoine tests
    assert that zero width themselves. A0's first IFI case used the unchanged barème and
    would have reported a rigorous zero about a case built so it could not move."""
    from impots import accuracy_cases

    swing = accuracy_cases.ifi_cell_bound_swing()
    low, high = swing("concentre"), swing("extremal")
    assert abs(high - low) > 100e6, (
        f"largeur {abs(high - low):,.0f} EUR : la réforme de référence ne coupe aucune "
        f"tranche, et l'encadrement ne mesure rien")


def test_every_unmeasured_source_names_why() -> None:
    """Three of the spec's declared sources have neither a law nor bounds today. Each must
    say so in its own words — an UNMEASURED row without a reason is an oversight."""
    from impots import accuracy_cases

    for case in accuracy_cases.REFERENCE_REFORMS:
        for source in accuracy_cases.sources_for(case, households=1000):
            if source.method == "unmeasured":
                assert len(source.unmeasured_reason) > 60, (case.key, source.key)


# ------------------------------------------------ A0 v2: the behavioural attribution

def test_pinning_a_degenerate_row_is_refused() -> None:
    """A row with low == high cannot change the sample: `Parameter.draw` returns a
    constant for it. Pinning it would score a rigorous zero, and a zero in a ranking
    reads as «measured, and it does not matter»."""
    from impots import accuracy_behavioural as ab
    from impots.behavioural.store import load

    store = load()
    degenerate = [k for k, p in store.parameters.items() if p.low == p.high]
    assert degenerate, "le store n'a plus de ligne dégénérée : ce test ne teste plus rien"
    with pytest.raises(ab.AttributionError, match="ligne constante"):
        ab.pin(store, degenerate[0])


def test_pinning_does_not_mutate_the_shared_store() -> None:
    """`store.load()` is memoised. A pin that mutated it would silently change every later
    evaluation in the process — the trap that made a live knob look dead in D-095, where a
    memoised baseline was compared against itself."""
    from impots import accuracy_behavioural as ab
    from impots.behavioural.store import load

    store = load()
    key = next(k for k, p in store.parameters.items() if p.low != p.high)
    before = (store.parameters[key].low, store.parameters[key].high)

    pinned = ab.pin(store, key)

    assert (store.parameters[key].low, store.parameters[key].high) == before
    assert pinned.parameters[key].low == pinned.parameters[key].high
    assert load().parameters[key].low == before[0], "le store mémoïsé a été muté"


def test_a_zero_width_band_is_refused_rather_than_attributed() -> None:
    """A pure transfer reform moves no revenue-band channel, so the published band has zero
    width. Sharing zero out between parameters would produce a ranking of nothing — which
    is exactly what the RSA case does, and it is refused by name."""
    from impots import accuracy_behavioural as ab

    class _Result:
        band = None
        grade = "sans objet"
        channels: typing.ClassVar[list[dict]] = []

    assert ab.band_width(_Result()) == 0.0


def test_the_attribution_refuses_an_empty_store() -> None:
    from impots import accuracy_behavioural as ab
    from impots.behavioural.store import Store

    with pytest.raises(ab.AttributionError, match="store vide"):
        ab.attribute("x", {}, store=Store(parameters={}))


# ------------------------------- the data dependency, decoupled where it was incidental

def test_a_structural_noop_is_refused_before_any_data_is_read(monkeypatch) -> None:
    """`central_for` chargeait les cellules AVANT de pouvoir constater qu'une réforme qui
    remet un paramètre à sa valeur en vigueur ne bouge rien. L'arbre de paramètres suffit
    à le prouver : le refus vient donc avant tout chargement, et ce test le garantit en
    faisant exploser l'échantillonneur s'il est appelé."""
    from impots import accuracy_cases

    def interdit(*_a, **_k):
        raise AssertionError("l'échantillonneur ne devait pas être construit")

    monkeypatch.setattr(accuracy_cases, "firm_placement_sampler", interdit)
    noop = accuracy_cases.ReferenceReform(
        key="noop", label="no-op", family="CVAE", chain="firm",
        knob="cvae_taux_max", value=0.0028)
    with pytest.raises(ValueError, match="n'est pas une réforme") as caught:
        accuracy_cases.central_for(noop)
    assert "sans tirer d'échantillon" in str(caught.value)


def test_the_measured_threshold_still_refuses_what_barely_moves(monkeypatch) -> None:
    """LA moitié qui serait devenue non testée. Le refus structurel intercepte maintenant
    le cas 0,0028 AVANT la mesure ; sans ce test, la branche `MOVES_EPSILON_EUR` — celle
    qui refuse une réforme réelle dont l'effet MESURÉ est négligeable — n'aurait plus aucun
    test qui la fasse tourner. L'échantillonneur est injecté : c'est la logique du seuil
    qui est testée ici, la mesure réelle l'est par le test suivant, sur les vraies cellules.
    """
    from impots import accuracy_cases

    monkeypatch.setattr(accuracy_cases, "firm_placement_sampler",
                        lambda knob, value: (lambda seed: 1e6))
    presque = accuracy_cases.ReferenceReform(
        key="presque", label="presque rien", family="CVAE", chain="firm",
        knob="cvae_taux_max", value=0.0029)
    assert not accuracy_cases.structural_noop(presque)
    with pytest.raises(ValueError, match="sous le seuil"):
        accuracy_cases.central_for(presque)


def test_a_real_reform_falls_through_to_the_measurement(monkeypatch) -> None:
    """La garde doit DISCRIMINER : une valeur qui n'est pas celle en vigueur n'est jamais
    refusée structurellement — elle est mesurée, et le chiffre mesuré est rendu."""
    from impots import accuracy_cases

    monkeypatch.setattr(accuracy_cases, "firm_placement_sampler",
                        lambda knob, value: (lambda seed: 4.2e9))
    case = accuracy_cases.reform("cvae")
    assert accuracy_cases.central_for(case) == 4.2e9


def test_no_committed_reference_reform_is_a_structural_noop() -> None:
    """Protège « les réformes réellement présentes dépassent MOVES_EPSILON_EUR » du côté
    structurel, sans donnée : aucune des réformes de référence ne remet un paramètre à sa
    valeur en vigueur. Le côté mesuré reste `test_every_cheap_reference_reform_actually_moves`,
    sur les vraies cellules."""
    from impots import accuracy_cases

    for case in accuracy_cases.REFERENCE_REFORMS:
        assert not accuracy_cases.structural_noop(case), case.key


def test_the_structural_check_is_exact_and_not_a_tolerance() -> None:
    """Dans le doute, on mesure. Une valeur voisine de celle en vigueur n'est PAS un no-op
    structurel : un faux refus serait pire qu'un chargement inutile."""
    from impots import accuracy_cases

    voisin = accuracy_cases.ReferenceReform(
        key="v", label="v", family="CVAE", chain="firm", knob="cvae_taux_max",
        value=0.0028 + 1e-12)
    assert not accuracy_cases.structural_noop(voisin)


def test_declaring_the_sources_of_a_case_reads_no_data(tmp_path, monkeypatch) -> None:
    """`sources_for` DÉCLARE des sources ; il ne doit pas exiger les données qu'il faut pour
    les TIRER. Le chemin des cellules pointe vers un fichier inexistant et le tirage des
    tranches IFI explose : la déclaration réussit quand même, et c'est le TIRAGE qui échoue
    — là où la donnée est réellement lue."""
    from impots import accuracy_cases

    monkeypatch.setattr(accuracy_cases, "FIRM_CELLS", tmp_path / "absent.json")

    def pas_de_tranches():
        raise FileNotFoundError("tranches IFI lues trop tôt")

    monkeypatch.setattr("impots.patrimoine.cells.cells", pas_de_tranches)

    firm = accuracy_cases.sources_for(accuracy_cases.reform("cvae"), households=10)
    placement = next(s for s in firm if s.method == "sampled")
    with pytest.raises(FileNotFoundError):
        placement.sample(1)

    ifi = accuracy_cases.sources_for(accuracy_cases.reform("ifi"), households=10)
    bound = next(s for s in ifi if s.method == "swing")
    with pytest.raises(FileNotFoundError, match="trop tôt"):
        bound.swing("concentre")


def test_the_lazy_sampler_reads_the_cells_once(monkeypatch) -> None:
    """Paresseux ne veut pas dire relu à chaque tirage : 128 tirages, un chargement.

    Écrit d'abord avec un seul tirage — ce qui ne pouvait pas voir une relecture au
    second, sous un nom qui prétendait le contraire. Deux tirages, sur le VRAI moteur
    entreprises et les cellules de la fixture : c'est la mise en cache qui est testée,
    pas les chiffres, qui ne disent rien de la France.
    """
    from impots import accuracy_cases
    from impots.entreprises import build as build_module

    vraie_lecture = build_module.load_cells
    lectures: list[str] = []

    def compter(path):
        lectures.append(str(path))
        return vraie_lecture(path)

    # Le chemin pointe vers un fichier qui EXISTE (la fixture), pour que le contrôle
    # d'existence du chargeur passe et que ce soit bien la lecture qui soit comptée.
    monkeypatch.setattr(accuracy_cases, "FIRM_CELLS", build_module.FIXTURE_CELLS)
    monkeypatch.setattr(build_module, "load_cells", compter)
    sample = accuracy_cases.firm_placement_sampler("cvae_taux_max", 0.005)
    assert lectures == [], "rien ne doit être lu à la construction"
    sample(1)
    sample(2)
    assert len(lectures) == 1


def test_a_parameter_that_changes_during_the_year_is_not_a_structural_noop(
        monkeypatch) -> None:
    """La seconde borne. Si le paramètre vaut la valeur de la réforme au 1er janvier mais
    change avant le 31 décembre, la réforme N'EST PAS neutre : elle l'écrase sur le reste
    de l'année. Le refus structurel doit alors se taire et laisser mesurer.

    Sans ce test, vérifier une seule des deux bornes passait inaperçu : l'arbre réel ne
    change pas `cvae_taux_max` en 2026, donc aucun autre test ne distingue les deux.
    """
    from impots import accuracy_cases

    def en_deux_temps(_parameters, _path):
        return lambda instant: 0.0028 if instant.endswith("-01-01") else 0.0040

    monkeypatch.setattr("impots.parameters.resolve", en_deux_temps)
    case = accuracy_cases.ReferenceReform(
        key="mi_annee", label="m", family="CVAE", chain="firm", knob="cvae_taux_max",
        value=0.0028)
    assert not accuracy_cases.structural_noop(case)
