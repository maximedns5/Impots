"""Le bruit de C1 aux seuils (D-282) : ce qui est mesuré n'est pas choisi à la main, et C1
y est chiffré par le code qui le chiffre dans la chaîne.

Les paquets sont ceux de l'étude dont la boîte porte une ligne de C1, lus sur les rapports
commités. Chaque échantillon et chaque pas est une passe des taux marginaux à part. C1 y
est la recette du canal lui-même, à θ = ½, et sa décomposition ménage par ménage doit
redonner cette recette. Le lanceur refuse un `src/` modifié ou un rapport déjà là.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import polars as pl
import pytest

from impots.api.schemas import ReformSpec
from impots.behavioural import channels
from impots.behavioural.store import load as load_store
from impots.dette import reference
from impots.population.runner import SAMPLE_SEED
from impots.predictif import recherche
from impots.predictif.theta import Theta

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bruit_c1.py"
START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("bruit_c1", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rows(report: dict) -> set[str]:
    return {part.split(" = ")[0] for search in report["searches"]
            for evaluation in search["evaluations"]
            for label, _ in evaluation.get("corners") or [] for part in label.split(", ")}


# --------------------------------------------------------------------------- #
# What is measured
# --------------------------------------------------------------------------- #
def test_the_menu_is_the_study_s_instruments_whose_box_reads_c1(script) -> None:
    expected = tuple(key for key in script.STUDY if _rows(json.loads(
        (script.REPORTS / f"exploration_etude_{key}.json").read_text(encoding="utf-8")))
        & set(channels.C1_KEYS))
    assert script.menu() == expected == ("decote", "ir")


def test_an_instrument_whose_box_reads_no_c1_row_is_not_measured(script, tmp_path) -> None:
    for key in script.STUDY:
        report = json.loads((script.REPORTS / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        if key == "decote":
            for search in report["searches"]:
                for evaluation in search["evaluations"]:
                    evaluation["corners"] = [
                        [", ".join(p for p in label.split(", ")
                                   if not p.startswith("eti_")), value]
                        for label, value in evaluation["corners"]]
        (tmp_path / f"exploration_etude_{key}.json").write_text(json.dumps(report),
                                                                encoding="utf-8")
    assert script.menu(tmp_path) == ("ir",)


def test_the_bundles_are_the_study_s_with_the_law_its_report_read(script) -> None:
    bundles = script.bundles()
    for key in ("decote", "ir"):
        report = json.loads((script.REPORTS / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        mine = [b for b in bundles if b.instrument == key]
        assert [b.knobs for b in mine] == [e["knobs"]
                                           for e in report["searches"][0]["evaluations"]]
        laws = [t["law"] for t in report["hypotheses"].get("transformations", [])]
        for bundle in mine:
            assert bundle.reform == recherche.reform_of(
                ReformSpec(), bundle.knobs, laws[0] if laws else None)
    assert len(bundles) == 8
    assert all(b.reform.ir_bareme for b in bundles if b.instrument == "ir")


def test_the_replications_are_the_samples_then_the_steps_in_both_frames(script) -> None:
    replications = script.replications()
    assert len(replications) == len(set(replications)) == 22
    for view in ("vieillie", "figee"):
        seeds = [s for v, s, p in replications if v == view and p == script.EMTR_STEP]
        assert seeds[0] == SAMPLE_SEED and len(set(seeds)) == 8
        steps = sorted(p for v, s, p in replications if v == view and s == SAMPLE_SEED)
        assert steps == [50.0, 100.0, 200.0, 500.0]


# --------------------------------------------------------------------------- #
# C1, as the channel prices it, and household by household
# --------------------------------------------------------------------------- #
def _households(rates: list[tuple[float, float]], weights: list[float],
                earners: list[int]) -> tuple[pl.DataFrame, pl.DataFrame]:
    ids = list(range(1, len(weights) + 1))
    households = pl.DataFrame({
        "household_id": ids, "weight": weights, "n_earners": earners,
        "emtr": [r[0] for r in rates], "emtr_reform": [r[1] for r in rates]})
    frame = pl.DataFrame({"household_id": ids,
                          "salaire_brut_annuel": [30_000.0 * (i % 3 + 1) for i in ids]})
    return households, frame


@pytest.fixture
def decote():
    return ReformSpec(decote_taux=0.2)


def test_c1_is_the_channel_s_receipt_and_its_households_add_up_to_it(script,
                                                                     decote) -> None:
    rates = [(0.30, 0.25), (0.53, 1.04), (1.10, 0.50), (0.40, 0.40), (0.96, 0.97),
             (0.20, 0.10)]
    households, frame = _households(rates, [10.0] * 5 + [40.0], [1, 1, 1, 1, 1, 0])
    store = load_store()
    found = script.decompose(households, frame, decote, store, Theta(common=0.5))
    from impots.api.main import eti_inputs
    from impots.predictif.theta import pinned

    earning = households.filter(pl.col("n_earners") > 0)
    channel = channels.elasticity_of_taxable_income(
        pinned(store, Theta(common=0.5)), decote, **eti_inputs(frame, earning), draws=1,
        rng=np.random.default_rng(0))
    assert found["c1_eur"] == pytest.approx(float(channel.draws[0]), rel=1e-12)
    assert found["households"] == 6 and found["earning"] == 5
    # The floor at 1 − τ = 0.05: households 2 and 3 cross it in one law, 5 in both.
    assert (found["floor_baseline"], found["floor_reform"]) == (2, 2)
    assert (found["floor_one"], found["floor_both"]) == (2, 1)


def test_a_household_s_term_is_the_worked_example_of_the_channel(script) -> None:
    """D-279's mechanism, by hand: a 41 % → 45 % rise on a 100 000 € base at e = 0.30
    gives back −947.76 € (the channel's own worked example)."""
    terms = script.terms(np.array([0.41]), np.array([0.45]), np.array([100_000.0]),
                         np.array([1.0]), np.array([0.30]))
    assert terms[0] == pytest.approx(-947.76, abs=0.01)


def test_the_floor_term_dominates_as_d279_said(script) -> None:
    """53 % → 104 %: the net-of-tax rate falls to its floor, 0.05, and the term is
    −2.24 × 1.04 of the base times e — the size D-279 read on a few households."""
    terms = script.terms(np.array([0.53]), np.array([1.04]), np.array([30_000.0]),
                         np.array([1.0]), np.array([1.0]))
    assert terms[0] == pytest.approx(30_000 * (np.log(0.05) - np.log(0.47)) * 1.04)


def test_the_standard_error_counts_the_sampled_households_only(script) -> None:
    """Certainty units keep their own weight and add no variance; the self-weighting
    ones, households without earners included at zero, give the with-replacement
    estimate of a total's variance."""
    contributions = np.array([5.0, -3.0, 0.0, 2.0, 100.0])
    weights = np.array([10.0, 10.0, 10.0, 10.0, 55.0])
    pps = contributions[:4]
    expected = np.sqrt(4 / 3 * np.sum((pps - pps.mean()) ** 2))
    assert script.standard_error(contributions, weights) == pytest.approx(expected)


def test_the_largest_terms_are_named_by_their_size(script, decote) -> None:
    rates = [(0.30, 0.25), (0.53, 1.04), (1.10, 0.50), (0.40, 0.38), (0.35, 0.30),
             (0.45, 0.44), (0.25, 0.20)]
    households, frame = _households(rates, [10.0] * 7, [1] * 7)
    found = script.decompose(households, frame, decote, load_store(), Theta(common=0.5),
                             top=2)
    terms = found["terms"]
    largest = sorted(terms, key=abs)[-2:]
    assert found["top_eur"] == pytest.approx(sum(largest))


# --------------------------------------------------------------------------- #
# κ: C1 in points of Δb, through the chain
# --------------------------------------------------------------------------- #
def test_kappa_is_the_chain_s_debt_per_euro_carried(script, monkeypatch) -> None:
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    one, two = script.kappa(cost=1e9), script.kappa(cost=2e9)
    assert one > 0 and two == pytest.approx(one, rel=1e-9)


# --------------------------------------------------------------------------- #
# The launcher
# --------------------------------------------------------------------------- #
@pytest.fixture
def launcher(script, monkeypatch, tmp_path):
    out = tmp_path / "bruit_c1"
    monkeypatch.setattr(script, "OUT", out)
    monkeypatch.setattr(script, "POLL", 0.0)
    state = SimpleNamespace(out=out, calls=[], live=0, most=0, codes={}, lengths={})

    class Process:
        def __init__(self, command, **kw):
            state.calls.append(command)
            state.live += 1
            state.most = max(state.most, state.live)
            self.code = state.codes.get(len(state.calls), 0)
            self.length = state.lengths.get(len(state.calls), 2)
            self.polled = 0

        def poll(self):
            self.polled += 1
            if self.polled < self.length:
                return None
            state.live -= 1
            return self.code

    monkeypatch.setattr(script.subprocess, "Popen", Process)
    monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    return state


def test_the_launcher_runs_every_replication_a_few_at_a_time(script, launcher) -> None:
    assert script.launch("ici", jobs=3) == 0
    assert len(launcher.calls) == 22 and launcher.most == 3
    asked = [(c[c.index("--cadre") + 1], int(c[c.index("--graine") + 1]),
              float(c[c.index("--pas") + 1])) for c in launcher.calls]
    assert asked == script.replications()
    assert all(c[c.index("--ou") + 1] == "ici" for c in launcher.calls)


def test_a_replication_that_fails_stops_the_ones_not_started(script, launcher,
                                                            capsys) -> None:
    launcher.codes[2] = 3
    assert script.launch("ici", jobs=1) == 3
    assert len(launcher.calls) == 2
    assert "les suivantes ne tournent pas" in capsys.readouterr().err


def test_no_replication_starts_after_one_fails_while_others_run(script,
                                                                launcher) -> None:
    launcher.codes[1], launcher.lengths[1], launcher.lengths[2] = 3, 1, 5
    assert script.launch("ici", jobs=2) == 3
    assert len(launcher.calls) == 2


@pytest.mark.parametrize("how, needle", [
    ("dirty", "modifications non commitées"),
    ("there", "un rapport n'est pas écrasé en silence"),
])
def test_the_launcher_refuses_before_any_pass(script, launcher, monkeypatch, capsys,
                                             how: str, needle: str) -> None:
    monkeypatch.setattr(recherche, "code_state",
                        lambda root=None: ("c0ffee", how == "dirty"))
    if how == "there":
        launcher.out.mkdir()
        (launcher.out / script.name("vieillie", SAMPLE_SEED, 100.0)).write_text("{}")
    assert script.launch("ici", jobs=3) == 1
    assert launcher.calls == [] and needle in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# The summary, read off the replications
# --------------------------------------------------------------------------- #
def _replication(script, view, seed, step, points, commit="c0ffee"):
    return {"view": view, "seed": seed, "step": step, "commit": commit, "kappa": 0.003,
            "bundles": [{"instrument": "decote", "knobs": {"decote_taux": 0.4},
                         "c1_points": points, "se_points": 0.01, "floor_one": 2,
                         "floor_one_points": points / 2, "top_points": points / 3}]}


def test_the_summary_reads_the_samples_and_the_steps_apart(script, tmp_path) -> None:
    values = dict(zip(script.SEEDS, [-0.01, -0.03, -0.02, 0.00, -0.04, -0.02, -0.01, -0.03],
                      strict=True))
    for view, seed, step in script.replications():
        points = values[seed] if step == script.EMTR_STEP else {50.0: -0.05, 200.0: 0.01,
                                                                 500.0: 0.02}[step]
        (tmp_path / script.name(view, seed, step)).write_text(
            json.dumps(_replication(script, view, seed, step, points)), encoding="utf-8")
    rows = script.summarise(tmp_path)
    assert len(rows) == 2
    row = rows[0]
    assert row["view"] == "vieillie" and row["c1_points"] == -0.01
    assert row["seeds_std"] == pytest.approx(np.std(list(values.values()), ddof=1))
    assert row["steps"] == {50.0: -0.05, 100.0: -0.01, 200.0: 0.01, 500.0: 0.02}


@pytest.mark.parametrize("how", ["missing", "two_commits"])
def test_the_summary_refuses_a_partial_or_mixed_measure(script, tmp_path, how) -> None:
    for index, (view, seed, step) in enumerate(script.replications()):
        if how == "missing" and index == 5:
            continue
        commit = "autre" if how == "two_commits" and index == 3 else "c0ffee"
        (tmp_path / script.name(view, seed, step)).write_text(
            json.dumps(_replication(script, view, seed, step, -0.01, commit)),
            encoding="utf-8")
    with pytest.raises(script.BruitError):
        script.summarise(tmp_path)


# --------------------------------------------------------------------------- #
# The refusals, before or during a replication
# --------------------------------------------------------------------------- #
def test_terms_that_do_not_add_up_to_the_channel_are_refused(script, monkeypatch,
                                                             decote) -> None:
    households, frame = _households([(0.30, 0.25), (0.40, 0.35)], [10.0, 10.0], [1, 1])
    monkeypatch.setattr(script, "terms", lambda *a: np.array([1e6, 0.0]))
    with pytest.raises(script.BruitError, match="ne serait pas C1"):
        script.decompose(households, frame, decote, load_store(), Theta(common=0.5))


def test_a_bundle_c1_does_not_read_is_refused(script) -> None:
    households, frame = _households([(0.30, 0.25)], [10.0], [1])
    with pytest.raises(script.BruitError, match="ne s'applique pas"):
        script.decompose(households, frame, ReformSpec(csg_activite_deductible=0.063),
                         load_store(), Theta(common=0.5))


@pytest.mark.parametrize("how, needle", [
    ("persistences", "les deux persistances"),
    ("transformations", "une au plus"),
])
def test_bundles_the_study_did_not_price_are_refused(script, tmp_path, how,
                                                     needle) -> None:
    for key in script.STUDY:
        report = json.loads((script.REPORTS / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        if key == "ir" and how == "persistences":
            report["searches"][1]["evaluations"][0]["knobs"] = {"ir_bareme_echelle": 0.9}
        if key == "ir" and how == "transformations":
            report["hypotheses"]["transformations"] *= 2
        (tmp_path / f"exploration_etude_{key}.json").write_text(json.dumps(report),
                                                                encoding="utf-8")
    with pytest.raises(script.BruitError, match=needle):
        script.bundles(tmp_path)


def test_requests_that_do_not_share_the_study_s_frame_are_refused(script,
                                                                  tmp_path) -> None:
    for key in ("decote", "ir"):
        request = json.loads((script.REQUESTS / f"{key}.json").read_text(encoding="utf-8"))
        if key == "ir":
            request["horizon"] = 9
        (tmp_path / f"{key}.json").write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(script.BruitError, match="ne partagent pas"):
        script._request(tmp_path)


@pytest.fixture
def stubbed_pass(script, monkeypatch):
    """`one` without data: a population of six households, the rates given per call."""
    from impots.api import main as api
    from impots.behavioural import emtr
    from impots.population import runner

    households, frame = _households([(0.30, 0.25), (0.53, 0.50), (0.41, 0.45),
                                     (0.20, 0.20), (0.35, 0.30), (0.10, 0.10)],
                                    [10.0] * 6, [1, 1, 1, 1, 1, 0])
    frame = frame.with_columns(pl.Series("person_id", list(range(1, 7))))
    monkeypatch.setattr(api, "_population_frame", lambda: frame)
    monkeypatch.setattr(runner, "subsample", lambda f, n, seed=0: f)
    monkeypatch.setattr(script, "kappa", lambda: 3e-12)
    monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    calls = []

    def compute(population, *, year, reform, sample, step):
        calls.append((year, reform, sample, step))
        shift = 0.01 if len(calls) == 3 and state.drift else 0.0
        return SimpleNamespace(households=households.with_columns(
            (pl.col("emtr") + shift).alias("emtr")))

    state = SimpleNamespace(calls=calls, drift=False)
    monkeypatch.setattr(emtr, "compute", compute)
    return state


def test_a_replication_prices_every_bundle_on_one_sample(script, stubbed_pass,
                                                         tmp_path) -> None:
    payload = script.one("figee", 3, 200.0, "ici", out=tmp_path)
    assert [c[1] for c in stubbed_pass.calls] == [b.reform for b in script.bundles()]
    assert {(c[0], c[2], c[3]) for c in stubbed_pass.calls} == {(2026, None, 200.0)}
    written = json.loads((tmp_path / script.name("figee", 3, 200.0)).read_text())
    assert written == json.loads(json.dumps(payload))
    assert (written["commit"], written["where"], written["seed"]) == ("c0ffee", "ici", 3)
    for row in written["bundles"]:
        assert row["c1_points"] == pytest.approx(-3e-12 * row["c1_eur"] * 100)
        assert row["se_points"] == pytest.approx(3e-12 * row["se_eur"] * 100)
        assert "terms" not in row


def test_a_baseline_that_moves_between_bundles_is_refused(script, stubbed_pass,
                                                          tmp_path) -> None:
    stubbed_pass.drift = True
    with pytest.raises(script.BruitError, match="taux de référence diffèrent"):
        script.one("figee", 3, 100.0, "ici", out=tmp_path)
    assert not (tmp_path / script.name("figee", 3, 100.0)).exists()


@pytest.mark.parametrize("view, needle", [("inconnu", "inconnu"), ("figee", "existe")])
def test_a_replication_refuses_before_any_pass(script, stubbed_pass, tmp_path, view,
                                               needle) -> None:
    (tmp_path / script.name("figee", 3, 100.0)).write_text("{}")
    with pytest.raises(script.BruitError, match=needle):
        script.one(view, 3, 100.0, "ici", out=tmp_path)
    assert stubbed_pass.calls == []
