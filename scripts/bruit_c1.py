"""Le bruit de C1 aux seuils (D-282) : la réponse du revenu imposable des paquets de
l'étude, sur d'autres échantillons des taux marginaux et à d'autres pas.

    python scripts/bruit_c1.py lancer --ou "..." [--jobs 3]   # les 22 réplications
    python scripts/bruit_c1.py resumer                         # le tableau, sur les rapports

C1 somme, sur les 3 000 ménages de l'échantillon des taux marginaux, le poids, l'assiette,
la variation du log du taux net et le taux de la réforme de chaque ménage (D-279). Le taux
est une différence finie : ce que garde le ménage de 100 € de salaire de plus. Au bord
d'un seuil, le pas le franchit, le taux saute, et le taux net tombe à son plancher. Une
poignée de ménages pèse alors autant que la moitié de la somme. Ce que l'on ne sait pas,
c'est de combien C1 changerait sur un autre échantillon, ou à un autre pas.

RIEN N'EST CHOISI À LA MAIN. `menu` lit les rapports commités de l'étude, et retient les
instruments dont la boîte porte une ligne de C1 ; `bundles`, leurs paquets, avec le droit
que le rapport a lu. Chaque réplication chiffre ces paquets sur un échantillon et à un pas,
dans un cadre : la vue vieillie de l'étude ou sa vue figée, en 2026.

C1 EST CELUI DE LA CHAÎNE. Les entrées sont celles que lit l'explorateur (`eti_inputs`),
la recette est celle du canal à θ = ½, et la décomposition ménage par ménage doit la
redonner, ou la réplication est refusée. κ, le Δb 2035 d'un euro de la première année
reporté, convertit la recette en points, dans le cadre de l'étude.

UNE PASSE PAR RÉPLICATION. Chaque réplication tourne dans son processus, quelques-unes à
la fois ; un `src/` modifié et un rapport déjà là sont refusés avant la première.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from impots import service

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "etude"
REPORTS = ROOT / "reports"
OUT = REPORTS / "bruit_c1"
sys.path.insert(0, str(ROOT / "src"))

from impots.behavioural.emtr import EMTR_STEP  # noqa: E402
from impots.population.runner import SAMPLE_SEED  # noqa: E402

#: The study's menu (D-237), in its order.
STUDY = ("csg", "allegements", "decote", "ir")
#: The two frames of the study's first year: the aged view and the frozen one.
FRAMES = ("vieillie", "figee")
#: The study's sample first, then seven others of the same size.
SEEDS = (SAMPLE_SEED, 1, 2, 3, 4, 5, 6, 7)
#: Steps besides the study's, on the study's sample.
STEPS = (50.0, 200.0, 500.0)
THETA = 0.5
#: The largest terms whose sum is reported.
TOP = 5
#: Seconds between two looks at the running replications.
POLL = 5.0


class BruitError(ValueError):
    """The measure would not be the one preregistered, or would not add up."""


@dataclass(frozen=True)
class Bundle:
    instrument: str
    knobs: dict[str, float]
    reform: Any


def _report(key: str, reports: Path) -> dict[str, Any]:
    return json.loads((reports / f"exploration_etude_{key}.json").read_text(encoding="utf-8"))


def _rows(report: dict[str, Any]) -> set[str]:
    return {part.split(" = ")[0] for search in report["searches"]
            for evaluation in search["evaluations"]
            for label, _ in evaluation.get("corners") or [] for part in label.split(", ")}


def menu(reports: Path = REPORTS) -> tuple[str, ...]:
    """The study's instruments whose box carries a row of C1, in the study's order."""
    from impots.behavioural import channels

    return tuple(key for key in STUDY
                 if _rows(_report(key, reports)) & set(channels.C1_KEYS))


def bundles(reports: Path = REPORTS) -> list[Bundle]:
    """Their bundles, as the study priced them: its request's base, the knobs of each
    evaluation, and the law its report read for a transformation."""
    from impots.api.schemas import ExplorationRequest, ReformSpec
    from impots.predictif import recherche

    found = []
    for key in menu(reports):
        report = _report(key, reports)
        request = ExplorationRequest.model_validate(report["request"])
        laws = [t["law"] for t in report["hypotheses"].get("transformations", [])]
        if len(laws) > 1:
            raise BruitError(f"{key} : {len(laws)} transformations, une au plus")
        evaluated = [[e["knobs"] for e in search["evaluations"]]
                     for search in report["searches"]]
        if any(knobs != evaluated[0] for knobs in evaluated):
            raise BruitError(f"{key} : les deux persistances n'ont pas évalué les mêmes "
                             f"paquets")
        for knobs in evaluated[0]:
            found.append(Bundle(key, dict(knobs), recherche.reform_of(
                request.base or ReformSpec(), knobs, laws[0] if laws else None)))
    return found


def replications() -> list[tuple[str, int, float]]:
    """(frame, seed, step): the samples at the study's step, then the steps on its
    sample, in each frame."""
    return ([(view, seed, EMTR_STEP) for view in FRAMES for seed in SEEDS]
            + [(view, SAMPLE_SEED, step) for view in FRAMES for step in STEPS])


def name(view: str, seed: int, step: float) -> str:
    return f"c1_{view}_{seed}_{int(step)}.json"


# --------------------------------------------------------------------------- #
# C1, household by household
# --------------------------------------------------------------------------- #
def terms(inputs: dict[str, np.ndarray], elasticity: np.ndarray) -> np.ndarray:
    """Each household's term of C1's sum, the channel's formula with its elasticity: the
    income tax's own rate in Δln, the total rate on the receipt (D-336)."""
    from impots.behavioural.channels import c1_terms

    own, _ = c1_terms(emtr_ir_baseline=inputs["emtr_ir_baseline"],
                      emtr_ir_reform=inputs["emtr_ir_reform"],
                      emtr_reform=inputs["emtr_reform"], taxable_base=inputs["taxable_base"],
                      weights=inputs["weights"])
    return own * elasticity


def standard_error(contributions: np.ndarray, weights: np.ndarray) -> float:
    """The with-replacement standard error of the sum over the self-weighting households,
    those at the sample's common weight; the certainty ones keep their own and add none
    (`runner.subsample`)."""
    rounded = np.round(weights, 6)
    values, counts = np.unique(rounded, return_counts=True)
    sampled = np.isclose(weights, values[np.argmax(counts)], rtol=1e-9)
    drawn = contributions[sampled]
    if drawn.size < 2:
        return 0.0
    return float(np.sqrt(drawn.size / (drawn.size - 1)
                         * np.sum((drawn - drawn.mean()) ** 2)))


def decompose(households: Any, frame: Any, reform: Any, store: Any, theta: Any,
              top: int = TOP) -> dict[str, Any]:
    """C1 at θ for one bundle on one EMTR pass: the channel's receipt, the households'
    terms that must add up to it, those at the net-of-tax floor, the largest, and the
    standard error of the sum. `households` are the pass's households, earners or not."""
    import polars as pl

    from impots.behavioural import channels
    from impots.predictif.theta import pinned, value_at
    from impots.service import eti_inputs

    earning = households.filter(pl.col("n_earners") > 0)
    inputs = eti_inputs(frame, earning)
    channel = channels.elasticity_of_taxable_income(
        pinned(store, theta), reform, **inputs, draws=1, rng=np.random.default_rng(0))
    if not channel.applies:
        raise BruitError(f"C1 ne s'applique pas à {reform} : {channel.message}")
    receipt = float(channel.draws[0])
    elasticity = np.where(
        inputs["top_decile"],
        value_at(store["eti_top_decile"], theta.for_row("eti_top_decile")),
        value_at(store["eti_all"], theta.for_row("eti_all")))
    own = terms(inputs, elasticity)
    if not np.isclose(own.sum(), receipt, rtol=1e-9, atol=1.0):
        raise BruitError(f"les termes des ménages somment à {own.sum():,.0f} €, le canal "
                         f"à {receipt:,.0f} € : la décomposition ne serait pas C1.")
    from impots.behavioural.channels import NET_OF_TAX_FLOOR

    floor_baseline = 1.0 - inputs["emtr_ir_baseline"] <= NET_OF_TAX_FLOOR
    floor_reform = 1.0 - inputs["emtr_ir_reform"] <= NET_OF_TAX_FLOOR
    one = floor_baseline ^ floor_reform
    largest = np.argsort(np.abs(own))[-top:]
    every = np.zeros(households.height)
    earning_rows = (households["n_earners"] > 0).to_numpy()
    every[earning_rows] = own
    return {
        "c1_eur": receipt, "households": int(households.height),
        "earning": int(earning.height),
        "se_eur": standard_error(every, households["weight"].to_numpy()),
        "floor_baseline": int(floor_baseline.sum()), "floor_reform": int(floor_reform.sum()),
        "floor_one": int(one.sum()), "floor_both": int((floor_baseline & floor_reform).sum()),
        "floor_one_eur": float(own[one].sum()), "top_eur": float(own[largest].sum()),
        "terms": own,
    }


# --------------------------------------------------------------------------- #
# κ, and one replication
# --------------------------------------------------------------------------- #
def _request(requests: Path = REQUESTS) -> Any:
    """The study's frame, which its requests share."""
    from impots.api.schemas import ExplorationRequest

    frames = []
    for key in ("decote", "ir"):
        request = ExplorationRequest.model_validate(
            json.loads((requests / f"{key}.json").read_text(encoding="utf-8")))
        frames.append(request.model_dump(include={"spending", "growth", "rate", "horizon",
                                                  "uprating", "theta", "target"}))
    if any(frame != frames[0] for frame in frames):
        raise BruitError("les requêtes de l'étude ne partagent pas leur cadre")
    return request


def kappa(cost: float = 1e9, requests: Path = REQUESTS) -> float:
    """Δb at the study's last year, a share of GDP, per euro of first-year cost carried
    at a constant share of GDP: the chain's own, in the study's frame. A receipt of C1
    lowers the debt by as much."""
    from impots.dette import reference
    from impots.predictif import chaine

    request = _request(requests)
    hypotheses = service.predictif_hypotheses(request)
    start = reference.start_from_accounts(chaine.START_YEAR)
    path = chaine.run(start, horizon=request.horizon,
                      costs=chaine.ReformCosts(by_year={start.year + 1: cost},
                                               carry=chaine.CARRY),
                      spending=hypotheses.spending, growth=hypotheses.growth,
                      rate=hypotheses.rate, theta=hypotheses.theta, store=hypotheses.store)
    return float(path.delta[-1]) / cost


def one(view: str, seed: int, step: float, where: str, out: Path = OUT) -> dict[str, Any]:
    """The study's C1 bundles, on one sample at one step, in one frame."""
    from impots import uprating as up
    from impots.behavioural import emtr
    from impots.population.runner import subsample
    from impots.predictif import chaine, recherche
    from impots.predictif.theta import Theta

    if view not in FRAMES:
        raise BruitError(f"cadre « {view} » inconnu : {FRAMES}")
    path = out / name(view, seed, step)
    if path.exists():
        raise BruitError(f"{path} existe : un rapport n'est pas écrasé en silence.")
    request = _request()
    hypotheses = service.predictif_hypotheses(request)
    year = chaine.START_YEAR + 1
    frame = service.population_frame()
    if view == "vieillie":
        frame = up.uprate(frame, year, hypotheses.uprating)
    drawn = subsample(frame, service.BEHAVIOURAL_EMTR_HOUSEHOLDS, seed=seed)
    k = kappa()
    theta = Theta(common=THETA)
    rows, baseline = [], None
    for bundle in bundles():
        result = emtr.compute(drawn, year=year, reform=bundle.reform, sample=None,
                              step=step)
        households = result.households
        rates = households["emtr"].to_numpy()
        if baseline is None:
            baseline = rates
        elif not np.array_equal(rates, baseline, equal_nan=True):
            raise BruitError("les taux de référence diffèrent d'un paquet à l'autre, sur "
                             "le même échantillon")
        found = decompose(households, frame, bundle.reform, hypotheses.store, theta)
        found.pop("terms")
        sha = hashlib.sha256(households["emtr_reform"].to_numpy().tobytes()).hexdigest()
        # A receipt lowers the debt: in points of Δb, C1 and its parts change sign.
        rows.append({"instrument": bundle.instrument, "knobs": bundle.knobs, **found,
                     **{key.replace("_eur", "_points"): -k * found[key] * 100
                        for key in ("c1_eur", "floor_one_eur", "top_eur")},
                     "se_points": k * found["se_eur"] * 100,
                     "reform_rates_sha": sha[:16]})
    commit, dirty = recherche.code_state(ROOT)
    payload = {
        "view": view, "seed": seed, "step": step, "year": year,
        "households": int(service.BEHAVIOURAL_EMTR_HOUSEHOLDS), "theta": THETA, "kappa": k,
        "frame_fingerprint": emtr.fingerprint(drawn.sort("person_id")),
        "baseline_rates_sha": hashlib.sha256(baseline.tobytes()).hexdigest()[:16],
        "commit": commit, "dirty": dirty, "where": where, "bundles": rows,
    }
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return payload


# --------------------------------------------------------------------------- #
# The launcher, and the summary
# --------------------------------------------------------------------------- #
def _command(view: str, seed: int, step: float, where: str) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve()), "une", "--cadre", view,
            "--graine", str(seed), "--pas", repr(step), "--ou", where]


def launch(where: str, jobs: int = 3) -> int:
    from impots.predictif import recherche

    _, dirty = recherche.code_state(ROOT)
    if dirty:
        print("src/ a des modifications non commitées : les rapports nommeraient un commit "
              "dont ils n'ont pas chiffré le code. Commiter d'abord.", file=sys.stderr)
        return 1
    there = [p.name for p in OUT.glob("c1_*.json")] if OUT.exists() else []
    if there:
        print(f"{OUT} porte déjà {there} : un rapport n'est pas écrasé en silence.",
              file=sys.stderr)
        return 1
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    pending, running, failed = list(replications()), [], 0
    while pending or running:
        while pending and len(running) < jobs and not failed:
            spec = pending.pop(0)
            print(f"== {name(*spec)}", flush=True)
            running.append((spec, subprocess.Popen(_command(*spec, where), cwd=ROOT,
                                                   env=env)))
        time.sleep(POLL)
        for item in list(running):
            code = item[1].poll()
            if code is None:
                continue
            running.remove(item)
            if code and not failed:
                failed = code
                print(f"{name(*item[0])} : la réplication a rendu {code}, les suivantes ne "
                      f"tournent pas.", file=sys.stderr)
        if failed and not running:
            break
    return failed


def summarise(out: Path = OUT) -> list[dict[str, Any]]:
    """Per frame and bundle: C1 in points of Δb on the study's sample and step, its spread
    over the samples, its standard error on the study's sample, its value at each step."""
    found = {}
    for spec in replications():
        path = out / name(*spec)
        if not path.exists():
            raise BruitError(f"{path} manque : la mesure serait partielle.")
        found[spec] = json.loads(path.read_text(encoding="utf-8"))
    commits = {payload["commit"] for payload in found.values()}
    if len(commits) != 1:
        raise BruitError(f"les réplications ont tourné sur {sorted(commits)}")
    rows = []
    for view in FRAMES:
        study = found[(view, SAMPLE_SEED, EMTR_STEP)]
        for index, bundle in enumerate(study["bundles"]):
            seeds = [found[(view, seed, EMTR_STEP)]["bundles"][index]["c1_points"]
                     for seed in SEEDS]
            steps = {step: found[(view, SAMPLE_SEED, step)]["bundles"][index]["c1_points"]
                     for step in sorted((EMTR_STEP, *STEPS))}
            rows.append({
                "view": view, "instrument": bundle["instrument"], "knobs": bundle["knobs"],
                "c1_points": bundle["c1_points"], "se_points": bundle["se_points"],
                "seeds_mean": float(np.mean(seeds)), "seeds_std": float(np.std(seeds, ddof=1)),
                "seeds_min": min(seeds), "seeds_max": max(seeds), "steps": steps,
                "floor_one": bundle["floor_one"],
                "floor_one_points": bundle["floor_one_points"],
                "top_points": bundle["top_points"],
            })
    return rows


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="what", required=True)
    run = sub.add_parser("lancer")
    run.add_argument("--ou", required=True, help="where the passes run, which each report says")
    run.add_argument("--jobs", type=int, default=3)
    single = sub.add_parser("une")
    single.add_argument("--cadre", required=True, choices=FRAMES)
    single.add_argument("--graine", type=int, required=True)
    single.add_argument("--pas", type=float, required=True)
    single.add_argument("--ou", required=True)
    sub.add_parser("resumer")
    parsed = parser.parse_args(args)
    try:
        if parsed.what == "lancer":
            return launch(parsed.ou, jobs=parsed.jobs)
        if parsed.what == "une":
            one(parsed.cadre, parsed.graine, parsed.pas, parsed.ou)
            return 0
        for row in summarise():
            print(json.dumps(row, ensure_ascii=False))
        return 0
    except BruitError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
