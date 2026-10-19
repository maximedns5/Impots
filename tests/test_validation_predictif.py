"""Phase 9 M6 §9 — the validation of a conditional prediction (`predictif.validation`, D-225).

§9.1, the chain's internal coherence: a null reform leaves the debt where the reference puts
it at every θ and under every scenario, behaviour and loop asked for; the GDP and the
balance the loop reads come from one Mésange table. (θ = 1/2 returning every row's
published centre is guard 5, in `test_theta.py`.)

§9.2, the CICE containment replayed with the θ box, preregistered: the rule was committed
before anything was computed, it has not moved since, and the outcome it records is the one
the code computes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from impots.dette import reference, scenarios
from impots.dette.path import SHIPPED
from impots.macro import mesange
from impots.predictif import chaine, validation
from impots.predictif.comportement import AtTheta
from impots.predictif.theta import MACRO_ROW, Theta
from macro_cases import synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = scenarios.GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = scenarios.RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu")
CASE = validation.PREREGISTERED / "cice_2013_boite_theta.yaml"


# --------------------------------------------------------------------------- #
# §9.1 — the internal coherence
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theta", [Theta(common=0.0), Theta(common=0.5), Theta(common=1.0),
                                   Theta(rows={"eti_all": 1.0, MACRO_ROW: 0.0},
                                         common=0.5)])
@pytest.mark.parametrize("rule", ["gele_en_volume", "part_pib_constante"])
def test_a_null_reform_is_null_at_every_theta_with_behaviour_and_loop(theta, rule) -> None:
    """§9.1. Behaviour at zero receipts and a zero impulse, under every θ and both rules:
    the reform path is the reference, to the float. A reference and a reform that did not
    run through the same path would fail here, and a loop that answered a null impulse
    with a measured zero rather than its absence would too."""
    costs = chaine.ReformCosts(
        by_year={2026: 0.0}, carry=chaine.CARRY,
        behavioural={2026: AtTheta(receipts=0.0, grade="in-support", box=(0.0, 0.0),
                                   claimed=("eti_all",))},
        impulses={2026: {"impot_sur_le_revenu": 0.0}})
    result = chaine.run(START, horizon=6, costs=costs, spending=SHIPPED[rule],
                        growth=GROWTH, rate=HELD, theta=theta, persistence=(
                            "tenu" if rule == "gele_en_volume" else None),
                        macro_store=synthetic_macro_store())
    assert result.delta == pytest.approx((0.0,) * 6, abs=1e-15)
    assert result.delta_interest == pytest.approx((0.0,) * 6, abs=1e-15)
    assert result.reform == pytest.approx(result.reference, abs=1e-15)
    assert "rétroaction" in result.absent


def test_the_loop_reads_gdp_and_balance_off_one_variant_table() -> None:
    """§9.1. The feedback and the GDP must come from the same model and the same variant.
    The store's two rows are held against the parsed variants: both off one `Variant`,
    hence one page, for every instrument the balance row carries."""
    pytest.importorskip("pypdf")
    if not (mesange.RAW / mesange.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le document Mésange")
    from impots.macro import store as macro_store

    tables = macro_store.load().tables
    variants = mesange.load()
    balance = tables["primary_balance_by_instrument"]
    gdp = tables["multiplier_by_instrument"]
    assert balance.source == gdp.source
    assert set(balance.values) <= set(gdp.values)
    for instrument, row in balance.values.items():
        variant = variants[instrument]
        assert row == variant.rows["solde_primaire_pts_pib"], instrument
        assert gdp.values[instrument] == variant.rows["gdp"], instrument


# --------------------------------------------------------------------------- #
# §9.2 — the preregistered containment
# --------------------------------------------------------------------------- #
def _history_truncated(path: Path) -> bool:
    """True when the oldest commit of the file is a shallow clone's boundary: its history
    may then be cut, and the first version seen may not be the registered one."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=validation.ROOT, capture_output=True,
                              text=True).stdout.strip()

    commits = git("log", "--format=%H", "--",
                  str(path.relative_to(validation.ROOT))).split()
    shallow = Path(validation.ROOT, git("rev-parse", "--git-path", "shallow"))
    boundary = set(shallow.read_text().split()) if shallow.exists() else set()
    return not commits or commits[-1] in boundary


def test_the_rule_was_registered_before_its_outcome_and_never_moved() -> None:
    """GUARD. The first commit carried the rule and no outcome; the rule has had one
    version since. A rule moved once the outcome was known would turn a finding into a
    pass and leave a file that looks exactly like an honest one."""
    if _history_truncated(CASE):
        pytest.skip("clone superficiel : le commit qui date l'enregistrement n'y est pas")
    validation.check_registered(CASE)
    versions = validation.revisions(CASE)
    assert versions[0]["outcome"] is None
    assert len(validation.rule_history(CASE)) == 1


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "PATH": "/usr/bin:/bin"})


def test_a_rule_moved_after_registration_or_an_outcome_registered_with_it_is_refused(
        tmp_path: Path) -> None:
    """The guard against its two failures, on a repository of its own: a rule widened
    in a second commit, and a case whose first commit already held its outcome."""
    _git(tmp_path, "init", "-q")
    case = tmp_path / "case.yaml"
    case.write_text(yaml.safe_dump({"rule": {"contains": "100 à 400"}, "outcome": None}))
    _git(tmp_path, "add", "case.yaml")
    _git(tmp_path, "commit", "-q", "-m", "enregistrement")
    validation.check_registered(case, root=tmp_path)
    case.write_text(yaml.safe_dump({"rule": {"contains": "50 à 500"},
                                    "outcome": {"contains": True}}))
    _git(tmp_path, "commit", "-q", "-am", "élargie après coup")
    with pytest.raises(validation.ValidationError, match="la règle a changé 1 fois"):
        validation.check_registered(case, root=tmp_path)
    late = tmp_path / "late.yaml"
    late.write_text(yaml.safe_dump({"rule": {"contains": "100 à 400"},
                                    "outcome": {"contains": True}}))
    _git(tmp_path, "add", "late.yaml")
    _git(tmp_path, "commit", "-q", "-m", "règle et résultat ensemble")
    with pytest.raises(validation.ValidationError, match="déjà un résultat"):
        validation.check_registered(late, root=tmp_path)
    with pytest.raises(validation.ValidationError, match="jamais été committé"):
        validation.check_registered(tmp_path / "absent.yaml", root=tmp_path)


def test_the_recorded_outcome_is_the_one_the_code_computes() -> None:
    """The finding stays true, or this test says so: the box for both variants, at
    θ = 0, 1/2 and 1, against the published 100 000 to 400 000 at three years. A change of
    multiplier, dispersion or convention that moved the box would fail here, and the case
    would have to be re-registered rather than re-read."""
    pytest.importorskip("pypdf")
    if not (mesange.RAW / mesange.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le document Mésange")
    from impots.macro import store as macro_store

    case = validation.load(CASE)
    episode = validation.load(validation.EPISODES / f"{case['episode']}.yaml")
    low = float(episode["expected"]["jobs_thousands_low"])
    high = float(episode["expected"]["jobs_thousands_high"])
    store = macro_store.load()
    outcome = case["outcome"]
    boxes = {v: validation.episode_box(episode, v, store) for v in validation.VARIANTS}
    for variant, box in boxes.items():
        recorded = outcome[variant]
        assert (box.at_zero, box.at_half, box.at_one) == pytest.approx(
            (recorded["at_zero"], recorded["at_half"], recorded["at_one"]), abs=0.05)
    assert all(b.contains(low, high) for b in boxes.values()) is outcome["contains"]
    assert all(b.centre_inside(low, high) for b in boxes.values()) is outcome["centre"]


def test_the_box_reads_the_published_range_from_the_episode_not_from_the_case() -> None:
    """The range the box is held against is the Phase 4 episode's, with its quotes: the
    case states a rule, it does not get to carry its own range."""
    case = validation.load(CASE)
    assert "100 000 à 400 000" in case["rule"]["contains"]
    assert "jobs_thousands_low" not in yaml.safe_dump(case)
    with pytest.raises(validation.ValidationError, match="variante"):
        validation.episode_box(validation.load(validation.EPISODES / "cice_2013.yaml"),
                               "ciblee", synthetic_macro_store())
