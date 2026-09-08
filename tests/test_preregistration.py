"""F1 — the pre-registered chiffrage harness.

THE FIRST TEST IN THIS FILE IS THE ONE THAT MATTERS. A grading harness whose red light
has never been seen is not a harness, it is a hope — the exact defect that let `make full`
report PASS for months while being structurally unable to report anything else (D-094).
So a stub case with a known miss must grade OUTSIDE before any real case is allowed in,
and `test_the_harness_grades_red` is that proof.

The rest divide into the arithmetic (which must survive a comparator of zero, of the wrong
sign, and both tolerance gates binding in turn) and the refusals (which are what make a
pre-registration mean anything at all).
"""

from __future__ import annotations

import subprocess

import pytest

from impots import preregistration as ch

TOLERANCE = ch.Tolerance(relative=0.20, absolute_eur=200e6,
                         rationale="±20 % ou ±200 M, le plus large : essai")


def comparator(published_eur: float, **overrides) -> ch.Comparator:
    base = dict(published_eur=published_eur, source="évaluation préalable, art. X",
                vintage="PLF 2027", perimeter="État, toutes APU",
                net_of="brut de tout effet induit", sign="yield",
                basis="annee-pleine")
    return ch.Comparator(**{**base, **overrides})


def case(mechanical_eur: float, published_eur: float | None = None, **overrides):
    kwargs = dict(
        case="essai", pre_registered="2026-10-05T09:00:00+00:00", commit="deadbeef",
        population_vintage="2024", sample=20_000, engine={"openfisca_france": "176.0.8"},
        mechanical_eur=mechanical_eur, tolerance=TOLERANCE, scenario="essai",
        comparator=None if published_eur is None else comparator(published_eur),
    )
    return ch.Chiffrage(**{**kwargs, **overrides})


# --------------------------------------------------------------------------- #
# The red light, before anything else
# --------------------------------------------------------------------------- #


def test_the_harness_grades_red():
    """A known miss must be graded OUTSIDE. Nothing else in this file matters if it isn't.

    Priced at 3.0 bn against an official 1.0 bn: three times the figure, on a tolerance of
    20 % or 200 M. Fails if `grade` ever returns "within" unconditionally, if the
    comparison is inverted, or if the allowance is computed from the SIMULATED figure —
    which would let a large enough error buy its own tolerance.
    """
    verdict = ch.grade(case(3.0e9, 1.0e9))
    assert verdict.verdict == "outside"
    assert verdict.direction == "au-dessus"
    assert verdict.gap_eur == pytest.approx(2.0e9)
    assert verdict.allowed_eur == pytest.approx(200e6)


def test_the_harness_also_grades_green():
    """The other half of the kill test: red for everything would prove nothing either."""
    verdict = ch.grade(case(1.05e9, 1.0e9))
    assert verdict.verdict == "within"


def test_the_allowance_is_computed_from_the_published_figure_not_ours():
    """Fails if the allowance is taken from `mechanical_eur`.

    A tolerance scaled by our own answer means a wilder estimate is judged more leniently,
    which is backwards: at 10 bn against a published 1 bn, a self-scaled 20 % would allow
    2 bn and call a tenfold miss a hit.
    """
    verdict = ch.grade(case(10.0e9, 1.0e9))
    assert verdict.allowed_eur == pytest.approx(200e6)
    assert verdict.verdict == "outside"


# --------------------------------------------------------------------------- #
# Question 1, applied at birth: the denominator that can go to zero
# --------------------------------------------------------------------------- #


def test_a_published_figure_of_zero_is_gradable():
    """A PLF article priced "sans impact budgétaire" publishes 0.

    A relative-only tolerance would demand infinite precision and grade every such case
    red for arithmetic reasons. Fails if `absolute_eur` stops being a floor — the D-093
    shape, avoided before the incident instead of after it.
    """
    verdict = ch.grade(case(-30e6, 0.0))
    assert verdict.verdict == "within"
    assert verdict.binding == "absolue"
    assert verdict.relative_gap is None, "un écart relatif à zéro n'est pas un nombre"


def test_a_small_published_figure_is_graded_on_the_absolute_gate():
    """50 M is inside the sampling noise of a 20 000-household draw, so the relative gate
    would be asking for precision the number does not have."""
    verdict = ch.grade(case(180e6, 50e6))
    assert verdict.binding == "absolue" and verdict.verdict == "within"


def test_a_large_published_figure_is_graded_on_the_relative_gate():
    verdict = ch.grade(case(2.3e9, 2.0e9))
    assert verdict.binding == "relative"
    assert verdict.allowed_eur == pytest.approx(400e6)
    assert verdict.verdict == "within"


def test_a_measure_that_raises_revenue_grades_on_the_magnitude():
    """Published figures are negative for a measure that brings money in. Fails if the
    allowance uses the signed value, which would make it negative and reject everything."""
    verdict = ch.grade(case(-1.4e9, -1.5e9))
    assert verdict.allowed_eur == pytest.approx(300e6)
    assert verdict.verdict == "within" and verdict.direction == "au-dessus"


def test_opposite_signs_are_reported_as_the_large_miss_they_are():
    verdict = ch.grade(case(0.4e9, -1.5e9))
    assert verdict.verdict == "outside"
    assert verdict.relative_gap == pytest.approx(1.2667, rel=1e-3)


@pytest.mark.parametrize("kwargs", [
    dict(relative=0.0, absolute_eur=1e6, rationale="r"),
    dict(relative=1.0, absolute_eur=1e6, rationale="r"),
    dict(relative=-0.1, absolute_eur=1e6, rationale="r"),
    dict(relative=0.2, absolute_eur=0.0, rationale="r"),
    dict(relative=0.2, absolute_eur=-1.0, rationale="r"),
    dict(relative=0.2, absolute_eur=1e6, rationale="   "),
])
def test_a_tolerance_that_measures_nothing_is_refused(kwargs):
    """0 can never be met, 1 admits everything, and one without a stated reason is a
    number chosen after the fact in spirit if not in time."""
    with pytest.raises(ch.ChiffrageError):
        ch.Tolerance(**kwargs)


# --------------------------------------------------------------------------- #
# The refusals
# --------------------------------------------------------------------------- #


def test_a_case_without_a_comparator_is_not_graded():
    with pytest.raises(ch.ChiffrageError, match="pas de comparateur"):
        ch.grade(case(1.0e9))


@pytest.mark.parametrize("field", ["source", "vintage", "perimeter", "net_of"])
def test_a_comparator_missing_its_discipline_is_refused(field):
    """Fails if any of the four descriptors becomes optional.

    Two budget figures can differ while both are right — gross or net of induced CSG, full
    year or the fraction the measure runs, the State or all administrations. A comparison
    that does not say which is not a comparison; it is a subtraction with a caption.
    """
    with pytest.raises(ch.ChiffrageError, match=field):
        ch.grade(case(1.0e9, 1.0e9, comparator=comparator(1.0e9, **{field: ""})))


def test_registering_the_same_case_twice_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    ch.register("essai", mechanical_eur=1.0e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=20_000, scenario="s",
                directory=tmp_path, now="2026-10-05T09:00:00+00:00")
    with pytest.raises(ch.ChiffrageError, match="existe déjà"):
        ch.register("essai", mechanical_eur=2.0e9, tolerance=TOLERANCE,
                    population_vintage="2024", sample=20_000, scenario="s",
                    directory=tmp_path, now="2026-10-05T10:00:00+00:00")


def test_a_case_that_says_nothing_about_what_was_priced_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    with pytest.raises(ch.ChiffrageError, match="ne dit pas ce qui a été chiffré"):
        ch.register("vide", mechanical_eur=1.0e9, tolerance=TOLERANCE,
                    population_vintage="2024", sample=20_000, directory=tmp_path)


@pytest.mark.parametrize("name", ["../evade", "a/b", "..", ""])
def test_a_case_name_that_is_a_path_is_refused(tmp_path, name):
    """Same rule as scenarios (D-094): a name is an identifier, never a path."""
    from impots.scenarios import ScenarioError

    with pytest.raises((ch.ChiffrageError, ScenarioError)):
        ch.load(name, tmp_path)


def test_a_malformed_case_file_is_a_chiffrage_error(tmp_path):
    (tmp_path / "casse.yaml").write_text("case: casse\n  bad indent:\n", encoding="utf-8")
    with pytest.raises(ch.ChiffrageError):
        ch.load("casse", tmp_path)


def test_an_incomplete_case_file_is_a_chiffrage_error(tmp_path):
    (tmp_path / "partiel.yaml").write_text("case: partiel\ncommit: abc\n", encoding="utf-8")
    with pytest.raises(ch.ChiffrageError, match="incomplet"):
        ch.load("partiel", tmp_path)


def test_a_case_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    ch.register("aller_retour", mechanical_eur=-1.234e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=20_000, scenario="plf_art3",
                behavioural={"low": -1.5e9, "high": -0.9e9, "grade": "illustrative"},
                note="essai", directory=tmp_path, now="2026-10-05T09:00:00+00:00")
    back = ch.load("aller_retour", tmp_path)
    assert back.mechanical_eur == pytest.approx(-1.234e9)
    assert back.tolerance.relative == pytest.approx(0.20)
    assert back.behavioural["grade"] == "illustrative"
    assert back.commit == "abc1234"
    assert back.pre_registered == "2026-10-05T09:00:00+00:00"
    assert back.comparator is None


# --------------------------------------------------------------------------- #
# "Declared before" as a property, not a habit
# --------------------------------------------------------------------------- #


def git_repo(tmp_path):
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True,
                       capture_output=True, text=True)
    run("init", "-q")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    (tmp_path / "chiffrages").mkdir()
    return run


def test_an_uncommitted_case_is_not_pre_registered(tmp_path, monkeypatch):
    """The commit IS the record. Fails if `verify_tolerance_unchanged` accepts a file with
    no history — a draft would then be gradeable, which is dating after the fact."""
    run = git_repo(tmp_path)
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    directory = tmp_path / "chiffrages"
    ch.register("brouillon", mechanical_eur=1.0e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=1, scenario="s", directory=directory)
    run("add", "-A")  # staged but never committed
    with pytest.raises(ch.ChiffrageError, match="jamais été committé"):
        ch.verify_tolerance_unchanged("brouillon", directory)


def test_a_committed_case_whose_tolerance_never_moved_is_accepted(tmp_path, monkeypatch):
    run = git_repo(tmp_path)
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    directory = tmp_path / "chiffrages"
    ch.register("stable", mechanical_eur=1.0e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=1, scenario="s", directory=directory)
    run("add", "-A")
    run("commit", "-q", "-m", "pre-register")
    ch.verify_tolerance_unchanged("stable", directory)  # must not raise

    # An edit that leaves the tolerance alone is fine — a comparator arriving later is
    # exactly the expected second commit.
    path = directory / "stable.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "note: ''", "note: 'comparateur saisi'"), encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "comparator")
    ch.verify_tolerance_unchanged("stable", directory)


def test_a_tolerance_widened_after_the_fact_is_caught(tmp_path, monkeypatch):
    """THE rule that makes the rest worth anything.

    Fails if `verify_tolerance_unchanged` reads the file instead of git history. A
    tolerance widened once the official figure is known turns every miss into a hit and
    leaves a file indistinguishable from an honest one — the file cannot catch this,
    because the file only ever shows the last version. Git remembers.
    """
    run = git_repo(tmp_path)
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    directory = tmp_path / "chiffrages"
    ch.register("elargi", mechanical_eur=3.0e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=1, scenario="s", directory=directory)
    run("add", "-A")
    run("commit", "-q", "-m", "pre-register")

    path = directory / "elargi.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "relative: 0.2", "relative: 0.9"), encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "oops")

    with pytest.raises(ch.ChiffrageError, match="tolérance a changé"):
        ch.verify_tolerance_unchanged("elargi", directory)


# --------------------------------------------------------------------------- #
# The report computes its own numbers
# --------------------------------------------------------------------------- #


def test_the_report_lists_ungraded_cases_rather_than_dropping_them(tmp_path, monkeypatch):
    """A record that lists only the cases with answers is not a record, it is a selection.

    Fails if `report` filters out cases with no comparator, or silently skips ones that
    refuse to grade.
    """
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    ch.register("en_attente", mechanical_eur=1.0e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=1, scenario="s", directory=tmp_path)
    # A second case that HAS a comparator but no git history: gradeable in arithmetic,
    # refused on integrity. Both must show, under their own headings.
    ch.register("jamais_committe", mechanical_eur=1.0e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=1, scenario="s", directory=tmp_path)
    path = tmp_path / "jamais_committe.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "comparator: null",
        "comparator:\n  published_eur: 1000000000.0\n  source: s\n  vintage: v\n"
        "  perimeter: p\n  net_of: n\n  retrieved: ''"), encoding="utf-8")

    text = ch.report(tmp_path)
    assert "en_attente" in text
    assert "En attente d'un comparateur" in text
    assert "Non notables" in text
    assert "jamais_committe" in text
    assert "jamais été committé" in text


def test_the_report_line_computes_its_own_numbers():
    """Fails if a number in the table is typed rather than derived — the mechanism the
    review asked to spread to every hand-written figure in reports/."""
    line = ch.grade(case(3.0e9, 1.0e9)).line()
    assert "+3.000" in line and "+1.000" in line and "+2.000" in line
    assert "+200.0%" in line
    assert "outside" in line


# --- alignment with the backward half ------------------------------------------------


def test_the_comparator_speaks_the_backtest_suite_s_vocabulary():
    """`sign` and `basis` mean the same thing here as in `behavioural.chiffrages`.

    Fails if this module drifts back to its own vocabulary. The published documents are
    inconsistent about sign — some print a cost as a positive number under a «coût»
    heading — so a figure that means different things in the two halves is a figure that
    will be compared wrongly.
    """
    from impots.behavioural.chiffrages import Published

    published = Published(amount_eur=2.0e9, sign="cost", basis="annee-pleine",
                          document="d", url="u")
    mine = comparator(2.0e9, sign="cost", basis="annee-pleine")
    assert mine.signed == published.signed == pytest.approx(-2.0e9)


@pytest.mark.parametrize("bad", [dict(sign="coût"), dict(basis="pleine")])
def test_an_unknown_sign_or_basis_is_refused(bad):
    """Fails if either becomes free text. Sign is carried, never inferred from the
    number's own sign — getting it wrong flips a case at twice the magnitude."""
    with pytest.raises(ch.ChiffrageError):
        comparator(1.0e9, **bad)


def test_a_lower_bound_case_is_judged_as_an_inequality():
    """`bound: lower` — we express only PART of what the published figure costs.

    Article 11 (CVAE) is the live case: one of six scale coefficients. Landing well
    BELOW the published figure is expected and passes; landing above it is a finding,
    because the case itself says that region is unreachable. Fails if `bound` is ignored
    and a symmetric window is used, which would fail the legitimate undershoot and pass
    the impossible overshoot.
    """
    undershoot = ch.grade(case(-0.7e9, -1.5e9, bound="lower"))
    assert undershoot.verdict == "within", "un sous-chiffrage attendu est refusé"
    overshoot = ch.grade(case(-2.5e9, -1.5e9, bound="lower"))
    assert overshoot.verdict == "outside", "un dépassement impossible est accepté"
    # And the symmetric default would judge the first one differently, which is the point.
    assert ch.grade(case(-0.7e9, -1.5e9)).verdict == "outside"


def test_the_mirror_flag_survives_a_round_trip(tmp_path, monkeypatch):
    """PLF 2026 article 9's trap: the tree already carries the article's end state, so
    the case must encode the repeal. Fails if `mirror` is dropped on save or load."""
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    ch.register("miroir", mechanical_eur=1.0e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=1, scenario="s",
                mirror=True, bound="lower", directory=tmp_path)
    back = ch.load("miroir", tmp_path)
    assert back.mirror is True and back.bound == "lower"
