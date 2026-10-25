"""C2's jobs per Md€ on the study's own pass, and what remains of the gap to the CAE (D-246, D-248).

Prices the FIRST bundle of a study request (its knob at `low`) the way `impots exploration`
does: the population aged to the first projected year, the quick tier of 20 000 households,
C2 at θ = ½ and at the two ends of its row. Then four readings of the same pass:

  - the chain's, through `api.main._employer_inputs`;
  - the reading before D-246, rebuilt here: every earner of the whole frame at the frame's
    weight, with no cost change outside the subsample;
  - the reading before D-248: the run's earners at the run's weight, each carrying their
    household's change in labour cost rather than their own;
  - what remains of the gap to a cut placed whole at the SMIC: where the knob puts its
    euros (the labour cost per job they reach) and C2's profile (its fade-out to 2 SMIC).

Run:  PYTHONPATH=src .venv/bin/python scripts/verify_c2_emploi.py etude/courbe/t_delta.json
      [vieillie|figee]
One population pass, several minutes and about 6.7 GB: run one at a time.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

from impots import uprating as uprating_module
from impots.api import main as api
from impots.api.schemas import HouseholdInput, ReformSpec
from impots.behavioural import channels
from impots.behavioural.store import load as load_store
from impots.dette.scenarios import GrowthScenario
from impots.engine import compute
from impots.predictif import annuel, chaine
from impots.predictif import indices as indices_module
from impots.predictif.theta import Theta, pinned


def main(path: str, view: str) -> dict[str, object]:
    study = json.loads(Path(path).read_text(encoding="utf-8"))
    (bound,) = study["bounds"]
    knob, value = bound["knob"], float(bound["low"])
    year = chaine.START_YEAR + 1  # the first projected year, as `impots exploration`

    uprating = annuel.uprating_for(
        GrowthScenario(study["growth"]["name"], study["growth"]["real"],
                       study["growth"]["prices"]),
        wage=study["uprating"]["wage"], source=study["uprating"]["source"],
        base_year=int(api.POPULATION_VINTAGE))
    reform = ReformSpec(**{knob: value})
    request = api._first_year_request(reform, year, True)
    frame = (uprating_module.uprate(api._population_frame(), year, uprating)
             if view == api.FIRST_YEAR_VIEW else api._population_frame())
    run, agg = api._run_population(request, frame)
    cost = float(agg.reform_cost)
    store = load_store()

    def c2(inputs: dict, theta: Theta) -> float:
        channel = indices_module._channel(store, theta, "c2_employment", reform, -cost,
                                          inputs)
        return float(channel["band"]["p50"])

    half = Theta(rows={}, common=0.5)
    chain = api._employer_inputs(request, run, agg)
    jobs = c2(chain, half)
    box = [c2(chain, Theta(rows={"employment_elasticity_smic": t}, common=0.5))
           for t in (0.0, 1.0)]

    households = run.households
    before = households["salaire_super_brut"].to_numpy()
    after = households["salaire_super_brut_reform"].to_numpy()
    rate = np.where(before > 0, (after - before) / np.maximum(before, 1e-9), 0.0)
    smic = api._smic_annual(year)
    by_household = dict(zip(households["household_id"].to_list(), rate, strict=False))

    # The reading before D-246, rebuilt: the whole frame, at its weight, household rates.
    everyone = frame.filter(pl.col("salaire_brut_annuel") > 0)
    jobs_old = c2({
        "smic_multiple": everyone["salaire_brut_annuel"].to_numpy() / smic,
        "relative_cost_change": np.array(
            [by_household.get(h, 0.0) for h in everyone["household_id"].to_list()]),
        "earner_weights": everyone["weight"].to_numpy(),
    }, half)
    sampled = everyone.filter(
        pl.col("household_id").is_in(households["household_id"].to_list()))

    # Each earner of the run, at the run's weight, with their own cost and their
    # household's rate, which is the reading before D-248.
    earners = run.persons.filter(pl.col("salaire_brut_annuel") > 0).join(
        households.select("household_id", "weight"), on="household_id", how="inner")
    weights = earners["weight"].to_numpy()
    salary = earners["salaire_brut_annuel"].to_numpy()
    own = earners["salaire_super_brut"].to_numpy()
    shift = earners["salaire_super_brut_reform"].to_numpy() - own
    household_rate = np.array([by_household[h] for h in earners["household_id"].to_list()])
    jobs_household_rate = c2({"smic_multiple": salary / smic,
                              "relative_cost_change": household_rate,
                              "earner_weights": weights}, half)

    cut = np.abs(np.where(own > 0, shift / np.maximum(own, 1e-9), 0.0))
    euros = weights * np.abs(shift)
    touched = float(np.sum(weights * cut))
    at_half = pinned(store, half)
    elasticity = at_half["employment_elasticity_smic"].central
    fadeout = at_half["employment_fadeout_smic_multiple"].central
    profile = channels.employment_elasticity_profile(
        salary / smic, elasticity, at_half["employment_elasticity_at_fadeout"].central,
        fadeout)

    one = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": smic, "annee_naissance": 1990}]})
    smic_job = float(compute(one, year, tier="light").baseline["salaire_super_brut"])
    per_bn = 1e9 / cost
    return {
        "knob": knob, "value": value, "view": view, "year": year, "cost_eur": cost,
        "jobs": jobs, "jobs_per_bn": jobs * per_bn,
        "box_per_bn": [b * per_bn for b in box],
        "before_d246_jobs_per_bn": jobs_old * per_bn,
        "before_d248_jobs_per_bn": jobs_household_rate * per_bn,
        "earners_frame_M": float(everyone["weight"].sum() / 1e6),
        "earners_sampled_at_frame_weight_M": float(sampled["weight"].sum() / 1e6),
        "earners_sampled_at_run_weight_M": float(weights.sum() / 1e6),
        "earners_cut_over_cost": float(euros.sum()) / cost,
        "smic_job_labour_cost_eur": smic_job,
        "per_bn_whole_cut_at_smic": -elasticity * 1e9 / smic_job,
        "labour_cost_per_job_reached_eur": float(euros.sum()) / touched,
        "per_bn_without_profile": -elasticity * touched * per_bn,
        "share_of_euros_above_fadeout": float(euros[salary / smic > fadeout].sum()
                                              / euros.sum()),
        "euro_weighted_elasticity": float(np.sum(euros * profile) / euros.sum()),
    }


if __name__ == "__main__":
    view = sys.argv[2] if len(sys.argv) > 2 else api.FIRST_YEAR_VIEW
    print(json.dumps(main(sys.argv[1], view), indent=1, ensure_ascii=False))
