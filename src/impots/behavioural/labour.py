"""Who the labour-supply channel prices, read off the population frame (Phase 9 M5, D-220).

C7 needs, for every person of the paper's sample, a group, gross earnings, a weight, the
household's marginal rate and the change in log net wage. This module builds those arrays
from the frame and the EMTR pass, and nothing else: the arithmetic is in `channels`.

THE SAMPLE IS A SAMPLE OF HOUSEHOLDS. « We only keep households where adults are aged
between 18 and 59, available for the labor market (not disabled, retired or in education)
and we exclude self-employed, farmers and "extreme" situations » (section 3). So a
household is in it when its reference person and partner, if any, are both of that band,
draw no pension (the frame's mark of the retired and the disabled), are not students and
are not self-employed — and an earner whose partner is 62 and retired is OUTSIDE, priced
at nothing and counted, because the paper never estimated anyone like them. The groups
are the paper's: a household with a partner is a couple — the paper says « couples »
without saying whether married only, and its tables say « married », so the frame's
partner is the nearest reading, not a sourced one; a reference person without one is
single. An adult child or another adult of the household (`enfant`, `autre`) is neither,
and is left outside too rather than guessed into a group.

Non-earners of the sample are not dropped by mistake: the total-hours elasticity is the
response of the group's AVERAGE hours, participation included, and applied to the group's
earnings the zeros contribute nothing either way.
"""

from __future__ import annotations

import numpy as np
import polars as pl

#: The paper's age band, inclusive (section 3).
SAMPLE_AGES = (18, 59)

#: The two household roles the paper's groups are made of.
COUPLE_ROLES = ("personne_de_reference", "conjoint")

#: What the frame says of an adult the paper's sample would not have kept.
OUT_OF_SAMPLE = (
    ~pl.col("age").is_between(*SAMPLE_AGES)
    | (pl.col("pension_annuelle") > 0)
    | (pl.col("statut_activite") == "student")
    | ((pl.col("statut_activite") == "employed") & ~pl.col("is_salarie"))
)

OUTSIDE = ""


def groups(frame: pl.DataFrame) -> pl.DataFrame:
    """person_id, household_id, salaire_brut_annuel, group — every earner of the age band.

    `group` is one of `channels.LABOUR_GROUPS`, or `OUTSIDE` for an earner of the band the
    paper's sample would not have kept.
    """
    low, high = SAMPLE_AGES
    member = pl.col("role_menage").is_in(COUPLE_ROLES)
    kept = ~(member & OUT_OF_SAMPLE).any().over("household_id")
    partnered = (pl.col("role_menage") == "conjoint").any().over("household_id")
    female = pl.col("sex") == "female"
    group = (
        pl.when(~member | ~kept).then(pl.lit(OUTSIDE))
        .when(partnered & female).then(pl.lit("femmes_en_couple"))
        .when(partnered).then(pl.lit("hommes_en_couple"))
        .when(female).then(pl.lit("femmes_seules"))
        .otherwise(pl.lit("hommes_seuls"))
    )
    return (
        frame.with_columns(group.alias("group"))
        .filter(pl.col("age").is_between(low, high) & (pl.col("salaire_brut_annuel") > 0))
        .select("person_id", "household_id", "salaire_brut_annuel", "group")
        .sort("person_id")
    )


def inputs(frame: pl.DataFrame, households: pl.DataFrame,
           delta_log_net: float) -> dict[str, np.ndarray]:
    """The `labour_*` arrays `band.compute` takes, for the households the EMTR pass priced.

    `households` is the EMTR pass's frame (household_id, weight, emtr_reform): its weight
    is the SUBSAMPLE's, which is the one that makes the sum a national figure. The change
    in log net wage is one number for everyone, read off the run's wage bill: near enough
    for the CSG on earnings, whose base is 98,25 % of the gross wage up to four social
    security ceilings and all of it above, so that a rate change moves every net wage by
    almost the same share.
    """
    persons = groups(frame).join(
        households.select("household_id", "weight", "emtr_reform"),
        on="household_id", how="inner",
    )
    return {
        "labour_group": persons["group"].to_numpy(),
        "labour_earnings": persons["salaire_brut_annuel"].to_numpy(),
        "labour_delta_log_net": np.full(persons.height, float(delta_log_net)),
        "labour_weights": persons["weight"].to_numpy(),
        "labour_emtr": persons["emtr_reform"].to_numpy(),
    }
