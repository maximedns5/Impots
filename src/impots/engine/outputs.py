"""The variable registry: what we extract, from which entity, over which period,
and with which sign (spec §3.3).

This is a closed list on purpose. Free-form variable access would let the API
surface 3 142 openfisca variables we have never checked, each with its own period
and sign convention.

Names that look right and are wrong: `irpp` no longer exists (it is
`impot_revenu_restant_a_payer`), prime d'activité is `ppa` not `prime_activite`,
and there is no marginal-rate variable at all — EMTR is a finite difference
(see `compute.emtr`).

**Signs, measured on openfisca-france 176.0.8**: `impot_revenu_restant_a_payer`,
`cotisations_salariales`, `cotisations_employeur`, `csg_*_salaire` and
`crds_salaire` all come out negative (money leaving the household). They are
negated exactly once, here, at the wrapper boundary — never again downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Entity = Literal["individu", "foyer_fiscal", "famille", "menage"]
Period = Literal["month", "year"]
Tier = Literal["light", "full"]


@dataclass(frozen=True)
class Row:
    key: str
    """Key in the wire format."""
    variable: str
    """OpenFisca variable name."""
    entity: Entity
    period: Period
    tier: Tier
    negate: bool
    """True when the engine reports this as a negative number and the wire format
    reports a positive magnitude."""
    money: bool = True
    """False for counts such as `nbptr`, which must not be formatted as EUR."""
    label: str = ""
    """French label for the UI."""


REGISTRY: tuple[Row, ...] = (
    # --- salary block: individu, monthly, summed over household members --------
    Row("salaire_brut", "salaire_de_base", "individu", "month", "light", False,
        label="Salaire brut"),
    Row("salaire_super_brut", "salaire_super_brut", "individu", "month", "light", False,
        label="Coût du travail (super-brut)"),
    Row("salaire_net", "salaire_net", "individu", "month", "light", False,
        label="Salaire net"),
    Row("salaire_imposable", "salaire_imposable", "individu", "month", "light", False,
        label="Salaire imposable"),
    Row("cotisations_salariales", "cotisations_salariales", "individu", "month", "light", True,
        label="Cotisations salariales"),
    Row("cotisations_employeur", "cotisations_employeur", "individu", "month", "light", True,
        label="Cotisations employeur"),
    # The allègements, made visible. `cotisations_employeur` above sums the GROSS
    # employer contributions and does not net them out — the reductions land in
    # `salaire_super_brut` instead. So a reader who moved an allègement knob and watched
    # the contributions row saw nothing move, while the labour cost had changed by
    # hundreds of euros. Three rows rather than one, matching the three knob families.
    Row("allegement_general", "allegement_general", "individu", "month", "light", False,
        label="Réduction générale de cotisations patronales"),
    Row("allegement_bandeau_maladie", "allegement_cotisation_maladie", "individu",
        "month", "light", False, label="Bandeau maladie"),
    Row("allegement_bandeau_famille", "allegement_cotisation_allocations_familiales",
        "individu", "month", "light", False, label="Bandeau famille"),
    # Pensions and unemployment benefit. Added because their reconciliation lines
    # passed a hardcoded `None` as the simulated value and no row extracted the
    # quantity — so the lines could never fill, and printed "calibrated (spent)"
    # anyway, which is the claim that a target was hit by a comparison that never
    # happened. The quantities were in the simulation the whole time.
    Row("retraite_imposable", "retraite_imposable", "individu", "month", "light", False,
        label="Pensions et retraites imposables"),
    Row("chomage_brut", "chomage_brut", "individu", "month", "light", False,
        label="Allocations chômage brutes"),
    # The invalidity pension, box 1AZ, as the wire format writes it (D-190). An input, so
    # reading it costs the light tier nothing; without a row, the pension behind an ASI
    # would be inside `revenu_disponible` with nothing on screen to show it. The population
    # writes no invalidity pension: its column is zero there.
    Row("pension_invalidite", "pensions_invalidite", "individu", "month", "light", False,
        label="Pension d'invalidité (montant déclaré)"),
    Row("csg_deductible", "csg_deductible_salaire", "individu", "month", "light", True,
        label="CSG déductible"),
    Row("csg_imposable", "csg_imposable_salaire", "individu", "month", "light", True,
        label="CSG imposable"),
    Row("crds", "crds_salaire", "individu", "month", "light", True,
        label="CRDS"),
    # The CSG on the sick pay, which correction 23 levies (D-306). A receipt of its own:
    # `csg_deductible` and `csg_imposable` are the salary's. Zero for a household that
    # carries no allowance, which is every one the wire format builds (D-307).
    Row("csg_ij", "csg_indemnites_journalieres", "individu", "month", "light", True,
        label="CSG des indemnités journalières"),
    # --- tax block: foyer fiscal, annual --------------------------------------
    Row("ir", "impot_revenu_restant_a_payer", "foyer_fiscal", "year", "light", True,
        label="Impôt sur le revenu"),
    Row("ir_avant_reductions", "ir_plaf_qf", "foyer_fiscal", "year", "light", False,
        label="IR après plafonnement du QF"),
    Row("parts_fiscales", "nbptr", "foyer_fiscal", "year", "light", False, money=False,
        label="Parts fiscales"),
    Row("revenu_fiscal_reference", "rfr", "foyer_fiscal", "year", "light", False,
        label="Revenu fiscal de référence"),
    # The niches (B3). Zero unless a household declares a base, which is exactly what
    # the population does — and reporting them as an explicit zero rather than not at
    # all is what makes the omission visible where a reader will look for it.
    #
    # Not negated: the engine already stores these positive, unlike
    # `impot_revenu_restant_a_payer`. And no double-count risk in the balance guard —
    # `ir` is already net of both, and it is `ir` the guard reconstitutes from.
    # The comparator for the published barème line: after décote, BEFORE the article
    # 199 réductions and crédits. Equal to `ir` exactly while no household declares a
    # niche, which is why the reconciliation got away with reading `ir` until B3's
    # imputation made the two differ — and made the barème line appear to improve from
    # +9.1 % to -1.7 % by comparing the wrong quantity.
    Row("ir_avant_niches", "ip_net", "foyer_fiscal", "year", "light", False,
        label="Impôt après décote, avant réductions et crédits"),
    Row("reductions", "reductions", "foyer_fiscal", "year", "light", False,
        label="Réductions d'impôt"),
    Row("credits_impot", "credits_impot", "foyer_fiscal", "year", "light", False,
        label="Crédits d'impôt"),
    # Capital income (D-248). Zero unless the population is given a base, which only
    # the opt-in imputation does. The PFU is a « dont » of `ir`, which already holds it:
    # it is shown, never added to the receipts. The social levies on that income are not
    # in `ir`, so they are a receipt of their own; the engine stores them negative.
    Row("pfu", "prelevement_forfaitaire_unique_ir", "foyer_fiscal", "year", "light",
        False, label="dont prélèvement forfaitaire unique (part IR)"),
    Row("prelevements_sociaux_capital", "prelevements_sociaux_revenus_capital",
        "foyer_fiscal", "year", "light", True,
        label="Prélèvements sociaux sur les revenus du capital"),
    # The dividends declared at the PFU, case 2DC: an input read back, not a levy. It is
    # the base the dividend channel C10 moves (D-249), and never a receipt.
    Row("dividendes", "f2dc", "foyer_fiscal", "year", "light", False,
        label="Dividendes déclarés (case 2DC)"),
    # The CDHR, from 2025 (D-250): it tops a high income's tax up to 20 % of its RFR, PFU
    # included. Not in `ir` — openfisca takes it out of disposable income beside it — so a
    # receipt of its own, stored negative. Zero without capital income: it is the levy
    # that takes a PFU cut back from the foyers it holds.
    Row("cdhr", "contribution_differentielle_hauts_revenus", "foyer_fiscal", "year",
        "light", True, label="Contribution différentielle sur les hauts revenus"),
    # --- benefits block: famille, monthly — full tier only ---------------------
    Row("af", "af", "famille", "month", "full", False,
        label="Allocations familiales"),
    # The AEEH, its compléments and the lone parent's majoration, as one amount for the
    # famille, the way openfisca computes it. Given a row when the wire format learned a
    # child's disability (D-191). No CRDS is levied on it, so it enters `revenu_disponible`
    # through `prestations_familiales` as it stands here.
    Row("aeeh", "aeeh", "famille", "month", "full", False,
        label="Allocation d'éducation de l'enfant handicapé"),
    Row("ppa", "ppa", "famille", "month", "full", False,
        label="Prime d'activité"),
    Row("rsa", "rsa", "famille", "month", "full", False,
        label="RSA"),
    # The ASS, on the individual who draws it, beside the RSA that tops it up. Given a row
    # when the wire format learned to open it (D-189). Zero over the population, which
    # declares nobody « en fin de droits ».
    Row("ass", "ass", "individu", "month", "full", False,
        label="Allocation de solidarité spécifique"),
    Row("aide_logement", "aide_logement", "famille", "month", "full", False,
        label="Aide au logement"),
    # The AAH and its complement, on the individual who receives them. Given rows when the
    # wire format learned to open them (D-184): without one, an AAH was a benefit inside
    # `revenu_disponible` that no reader could see. `caah` is the complement as paid since
    # December 2019, the majoration pour la vie autonome times its eligibility; openfisca's
    # own `mva` is the amount before that test.
    Row("aah", "aah", "individu", "month", "full", False,
        label="Allocation aux adultes handicapés"),
    Row("mva", "caah", "individu", "month", "full", False,
        label="Majoration pour la vie autonome"),
    # The ASPA, on the famille, as openfisca pays it. Given a row when the page learned to
    # take a pension (D-186): a pensioner at its level had a disposable income the table
    # could not account for, by exactly the ASPA.
    Row("aspa", "aspa", "famille", "month", "full", False,
        label="Allocation de solidarité aux personnes âgées"),
    # The ASI, on the individual who receives it, as openfisca pays it once capped for the
    # lone beneficiary of a couple (correction 10). Given a row when the wire format learned to
    # open it with an invalidity pension (D-190). Zero in the population, which has none.
    Row("asi", "asi", "individu", "month", "full", False,
        label="Allocation supplémentaire d'invalidité"),
    # Complément familial and allocation de soutien familial. Itemised for the third
    # time in this project's history for the same reason, and found the same way: the
    # double-entry guard. Both are means-tested, so a CSG reform that changes net income
    # moves them; both sit inside `revenu_disponible` through `prestations_familiales`;
    # neither had a row. Measured on a national CSG reform, `cf` moved 3.59 M EUR and
    # `asf` 8.23 M EUR, and the guard's unexplained residual was 11.86 M EUR — the sum,
    # to within rounding. Cf. `aefa` above and the benefit-side CRDS below: a benefit the
    # runner does not report is a benefit the cost reconstitution cannot see.
    Row("cf", "cf", "famille", "month", "full", False,
        label="Complément familial"),
    Row("asf", "asf", "famille", "month", "full", False,
        label="Allocation de soutien familial"),
    # The prime de Noël. Itemised because the double-entry guard found it leaking:
    # raising the RSA base brings households into ELIGIBILITY, and eligibility carries
    # this flat 152.45 EUR with it. It sits inside `revenu_disponible` through
    # `minima_sociaux`, so a reconstitution from the four other transfers came up
    # 36 M EUR short on a national RSA reform — 0.99 %, ten times the tolerance.
    Row("aefa", "aefa", "famille", "year", "full", False,
        label="Aide exceptionnelle de fin d'année (prime de Noël)"),
    # CRDS levied ON the benefits above. Negative as openfisca stores it, because a
    # benefit's net value is `gross + crds`. Itemised for the same reason as `aefa`:
    # `revenu_disponible` carries benefits NET, the population reports them GROSS, and
    # the 0.5 % between the two is exactly what made a national AF reform miss by
    # 0.50 %. Entered on the transfer side, where it nets the benefit down to what the
    # state actually bears.
    Row("crds_pfam", "crds_pfam", "famille", "year", "full", False,
        label="CRDS sur prestations familiales"),
    Row("crds_logement", "crds_logement", "famille", "month", "full", False,
        label="CRDS sur aides au logement"),
    Row("crds_mini", "crds_mini", "famille", "month", "full", False,
        label="CRDS sur minima sociaux"),
    # Wealth tax. NEGATED: openfisca stores taxes as negative, and every other tax row
    # here is reported positive. Full tier only — it costs a foyer-level pass and is
    # zero for all but ~186 000 foyers nationally.
    Row("ifi", "isf_ifi", "foyer_fiscal", "year", "full", True,
        label="Impôt sur la fortune immobilière"),
    # --- bottom line: ménage, annual — full tier only --------------------------
    Row("revenu_disponible", "revenu_disponible", "menage", "year", "full", False,
        label="Revenu disponible"),
)

BY_KEY: dict[str, Row] = {row.key: row for row in REGISTRY}
LIGHT_ROWS: tuple[Row, ...] = tuple(r for r in REGISTRY if r.tier == "light")
FULL_ROWS: tuple[Row, ...] = REGISTRY


def rows_for(tier: Tier) -> tuple[Row, ...]:
    """The registry rows a given tier computes.

    `light` deliberately stops at the foyer fiscal: touching `revenu_disponible`
    or any famille variable triggers the whole benefits cascade and turns a 0.5 s
    request into a 3 s one.

    One exception, by law: an adult in « fin de droits ». The income tax reads the ASS
    (D-192), which reads the famille's resources and, for its eligibility, the AAH and the
    ASI, so that household's light tier costs about what its full tier does. It still
    reaches none of the benefits the ASS tops up.
    """
    return LIGHT_ROWS if tier == "light" else FULL_ROWS


def extract(simulation: Any, year: int, tier: Tier, debug: bool = False) -> dict[str, Any]:
    """Read the registry off a built Simulation and normalise it.

    Monthly variables are annualised with `calculate_add`; annual variables use
    `calculate` (calling `calculate` on a monthly variable raises). Individual
    variables are summed across household members — children contribute 0 salary,
    which is what makes the sum the household total.
    """
    period = str(year)
    values: dict[str, Any] = {}
    raw: dict[str, float] = {}

    for row in rows_for(tier):
        array = (
            simulation.calculate_add(row.variable, period)
            if row.period == "month"
            else simulation.calculate(row.variable, period)
        )
        total = float(array.sum()) if row.entity == "individu" else float(array[0])
        raw[row.key] = round(total, 2)
        # `+ 0.0` collapses IEEE negative zero: a household that owes no tax must
        # serialise as 0.0, not -0.0.
        values[row.key] = round(-total if row.negate else total, 2) + 0.0

    if debug:
        values["raw"] = raw
    return values


def check_registry(tax_benefit_system: Any) -> list[str]:
    """Assert every registry row still matches the engine. Returns a list of
    problems, empty when the registry is sound.

    A weekly openfisca release can rename a variable or move it between entities;
    this turns that into a named test failure instead of a silent zero.
    """
    problems: list[str] = []
    for row in REGISTRY:
        variable = tax_benefit_system.variables.get(row.variable)
        if variable is None:
            problems.append(f"{row.key}: variable {row.variable!r} no longer exists")
            continue
        if variable.entity.key != row.entity:
            problems.append(
                f"{row.key}: {row.variable} is on entity {variable.entity.key!r}, "
                f"registry says {row.entity!r}"
            )
        actual_period = str(variable.definition_period).lower()
        if actual_period != row.period:
            problems.append(
                f"{row.key}: {row.variable} has period {actual_period!r}, "
                f"registry says {row.period!r}"
            )
    for dead in ("irpp", "prime_activite", "taux_marginal_imposition"):
        if tax_benefit_system.variables.get(dead) is not None:
            problems.append(f"{dead!r} exists again — the registry comment is now wrong")
    return problems
